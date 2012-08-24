#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time, operator
from threading import RLock
from io import BytesIO
from collections import namedtuple

from calibre import prints
from calibre.constants import plugins
from calibre.ptempfile import SpooledTemporaryFile
from calibre.devices.errors import OpenFailed, DeviceError
from calibre.devices.mtp.base import MTPDeviceBase, synchronous
from calibre.devices.mtp.filesystem_cache import FilesystemCache

MTPDevice = namedtuple('MTPDevice', 'busnum devnum vendor_id product_id '
        'bcd serial manufacturer product')

def fingerprint(d):
    return MTPDevice(d.busnum, d.devnum, d.vendor_id, d.product_id, d.bcd,
            d.serial, d.manufacturer, d.product)

class MTP_DEVICE(MTPDeviceBase):

    supported_platforms = ['linux']

    def __init__(self, *args, **kwargs):
        MTPDeviceBase.__init__(self, *args, **kwargs)
        self.libmtp = None
        self.detect_cache = {}

        self.dev = None
        self._filesystem_cache = None
        self.lock = RLock()
        self.blacklisted_devices = set()
        self.ejected_devices = set()
        self.currently_connected_dev = None

    def set_debug_level(self, lvl):
        self.libmtp.set_debug_level(lvl)

    def report_progress(self, sent, total):
        try:
            p = int(sent/total * 100)
        except ZeroDivisionError:
            p = 100
        if self.progress_reporter is not None:
            self.progress_reporter(p)

    @synchronous
    def detect_managed_devices(self, devices_on_system, force_refresh=False):
        if self.libmtp is None: return None
        # First remove blacklisted devices.
        devs = set()
        for d in devices_on_system:
            fp = fingerprint(d)
            if fp not in self.blacklisted_devices:
                devs.add(fp)

        # Clean up ejected devices
        self.ejected_devices = devs.intersection(self.ejected_devices)

        # Check if the currently connected device is still present
        if self.currently_connected_dev is not None:
            return (self.currently_connected_dev if
                    self.currently_connected_dev in devs else None)

        # Remove ejected devices
        devs = devs - self.ejected_devices

        # Now check for MTP devices
        if force_refresh:
            self.detect_cache = {}
        cache = self.detect_cache
        for d in devs:
            ans = cache.get(d, None)
            if ans is None:
                ans = self.libmtp.is_mtp_device(d.busnum, d.devnum,
                        d.vendor_id, d.product_id)
                cache[d] = ans
            if ans:
                return d

        return None

    @synchronous
    def create_device(self, connected_device):
        d = connected_device
        return self.libmtp.Device(d.busnum, d.devnum, d.vendor_id,
                d.product_id, d.manufacturer, d.product, d.serial)

    @synchronous
    def eject(self):
        if self.currently_connected_dev is None: return
        self.ejected_devices.add(self.currently_connected_dev)
        self.post_yank_cleanup()

    @synchronous
    def post_yank_cleanup(self):
        self.dev = self._filesystem_cache = self.current_friendly_name = None
        self.currently_connected_dev = None

    @synchronous
    def startup(self):
        p = plugins['libmtp']
        self.libmtp = p[0]
        if self.libmtp is None:
            print ('Failed to load libmtp, MTP device detection disabled')
            print (p[1])

        for x in vars(self.libmtp):
            if x.startswith('LIBMTP'):
                setattr(self, x, getattr(self.libmtp, x))

    @synchronous
    def shutdown(self):
        self.dev = self._filesystem_cache = None

    def format_errorstack(self, errs):
        return '\n'.join(['%d:%s'%(code, msg.decode('utf-8', 'replace')) for
            code, msg in errs])

    @synchronous
    def open(self, connected_device, library_uuid):
        self.dev = self._filesystem_cache = None
        try:
            self.dev = self.create_device(connected_device)
        except self.libmtp.MTPError:
            # Give the device some time to settle
            time.sleep(2)
            try:
                self.dev = self.create_device(connected_device)
            except self.libmtp.MTPError:
                # Black list this device so that it is ignored for the
                # remainder of this session.
                self.blacklisted_devices.add(connected_device)
                raise OpenFailed('%s is not a MTP device'%(connected_device,))
        except TypeError:
            self.blacklisted_devices.add(connected_device)
            raise OpenFailed('')

        storage = sorted(self.dev.storage_info, key=operator.itemgetter('id'))
        if not storage:
            self.blacklisted_devices.add(connected_device)
            raise OpenFailed('No storage found for device %s'%(connected_device,))
        self._main_id = storage[0]['id']
        self._carda_id = self._cardb_id = None
        if len(storage) > 1:
            self._carda_id = storage[1]['id']
        if len(storage) > 2:
            self._cardb_id = storage[2]['id']
        self.current_friendly_name = self.dev.friendly_name

    @property
    def filesystem_cache(self):
        if self._filesystem_cache is None:
            with self.lock:
                storage, all_items, all_errs = [], [], []
                for sid, capacity in zip([self._main_id, self._carda_id,
                    self._cardb_id], self.total_space()):
                    if sid is None: continue
                    name = _('Unknown')
                    for x in self.dev.storage_info:
                        if x['id'] == sid:
                            name = x['name']
                            break
                    storage.append({'id':sid, 'size':capacity,
                        'is_folder':True, 'name':name, 'can_delete':False,
                        'is_system':True})
                    items, errs = self.dev.get_filesystem(sid)
                    all_items.extend(items), all_errs.extend(errs)
                if not all_items and all_errs:
                    raise DeviceError(
                            'Failed to read filesystem from %s with errors: %s'
                            %(self.current_friendly_name,
                                self.format_errorstack(all_errs)))
                if all_errs:
                    prints('There were some errors while getting the '
                            ' filesystem from %s: %s'%(
                                self.current_friendly_name,
                                self.format_errorstack(all_errs)))
                self._filesystem_cache = FilesystemCache(storage, all_items)
        return self._filesystem_cache

    @synchronous
    def get_device_information(self, end_session=True):
        d = self.dev
        return (self.current_friendly_name, d.device_version, d.device_version, '')

    @synchronous
    def card_prefix(self, end_session=True):
        ans = [None, None]
        if self._carda_id is not None:
            ans[0] = 'mtp:::%d:::'%self._carda_id
        if self._cardb_id is not None:
            ans[1] = 'mtp:::%d:::'%self._cardb_id
        return tuple(ans)

    @synchronous
    def total_space(self, end_session=True):
        ans = [0, 0, 0]
        for s in self.dev.storage_info:
            i = {self._main_id:0, self._carda_id:1,
                    self._cardb_id:2}.get(s['id'], None)
            if i is not None:
                ans[i] = s['capacity']
        return tuple(ans)

    @synchronous
    def free_space(self, end_session=True):
        self.dev.update_storage_info()
        ans = [0, 0, 0]
        for s in self.dev.storage_info:
            i = {self._main_id:0, self._carda_id:1,
                    self._cardb_id:2}.get(s['id'], None)
            if i is not None:
                ans[i] = s['freespace_bytes']
        return tuple(ans)

    @synchronous
    def create_folder(self, parent, name):
        if not parent.is_folder:
            raise ValueError('%s is not a folder'%(parent.full_path,))
        e = parent.folder_named(name)
        if e is not None:
            return e
        ename = name.encode('utf-8') if isinstance(name, unicode) else name
        sid, pid = parent.storage_id, parent.object_id
        if pid == sid:
            pid = 0
        ans, errs = self.dev.create_folder(sid, pid, ename)
        if ans is None:
            raise DeviceError(
                    'Failed to create folder named %s in %s with error: %s'%
                    (name, parent.full_path, self.format_errorstack(errs)))
        return parent.add_child(ans)

    @synchronous
    def put_file(self, parent, name, stream, size, callback=None, replace=True):
        e = parent.folder_named(name)
        if e is not None:
            raise ValueError('Cannot upload file, %s already has a folder named: %s'%(
                parent.full_path, e.name))
        e = parent.file_named(name)
        if e is not None:
            if not replace:
                raise ValueError('Cannot upload file %s, it already exists'%(
                    e.full_path,))
            self.delete_file_or_folder(e)
        ename = name.encode('utf-8') if isinstance(name, unicode) else name
        sid, pid = parent.storage_id, parent.object_id
        if pid == sid:
            pid = 0

        ans, errs = self.dev.put_file(sid, pid, ename, stream, size, callback)
        if ans is None:
            raise DeviceError('Failed to upload file named: %s to %s: %s'
                    %(name, parent.full_path, self.format_errorstack(errs)))
        return parent.add_child(ans)

    @synchronous
    def get_file(self, f, stream=None, callback=None):
        if f.is_folder:
            raise ValueError('%s if a folder'%(f.full_path,))
        if stream is None:
            stream = SpooledTemporaryFile(5*1024*1024, '_wpd_receive_file.dat')
            stream.name = f.name
        ok, errs = self.dev.get_file(f.object_id, stream, callback)
        if not ok:
            raise DeviceError('Failed to get file: %s with errors: %s'%(
                f.full_path, self.format_errorstack(errs)))
        return stream

    @synchronous
    def delete_file_or_folder(self, obj):
        if obj.deleted:
            return
        if not obj.can_delete:
            raise ValueError('Cannot delete %s as deletion not allowed'%
                    (obj.full_path,))
        if obj.is_system:
            raise ValueError('Cannot delete %s as it is a system object'%
                    (obj.full_path,))
        if obj.files or obj.folders:
            raise ValueError('Cannot delete %s as it is not empty'%
                    (obj.full_path,))
        parent = obj.parent
        ok, errs = self.dev.delete_object(obj.object_id)
        if not ok:
            raise DeviceError('Failed to delete %s with error: %s'%
                (obj.full_path, self.format_errorstack(errs)))
        parent.remove_child(obj)

if __name__ == '__main__':
    BytesIO
    class PR:
        def report_progress(self, sent, total):
            print (sent, total, end=', ')

    from pprint import pprint
    dev = MTP_DEVICE(None)
    dev.startup()
    from calibre.devices.scanner import linux_scanner
    devs = linux_scanner()
    cd = dev.detect_managed_devices(devs)
    dev.open(cd, 'xxx')
    d = dev.dev
    print ("Opened device:", dev.get_gui_name())
    print ("Storage info:")
    pprint(d.storage_info)
    print("Free space:", dev.free_space())
    # print (d.create_folder(dev._main_id, 0, 'testf'))
    # raw = b'test'
    # fname = b'moose.txt'
    # src = BytesIO(raw)
    # print (d.put_file(dev._main_id, 0, fname, src, len(raw), PR()))
    # with open('/tmp/flint.epub', 'wb') as f:
    #     print(d.get_file(786, f, PR()))
    # print()
    # with open('/tmp/bleak.epub', 'wb') as f:
    #     print(d.get_file(601, f, PR()))
    # print()

    dev.filesystem_cache.dump()

    # print (dev.filesystem_cache.entries[0].files[0])
    # print (dev.filesystem_cache.entries[0].folders[0])
    dev.set_debug_level(dev.LIBMTP_DEBUG_ALL)
    del d
    dev.shutdown()

