__license__   = 'GPL v3'
__copyright__ = '''2009, John Schember <john at nachtimwald.com>
                    and Kovid Goyal <kovid@kovidgoyal.net>'''
'''
Generic device driver. This is not a complete stand alone driver. It is
intended to be subclassed with the relevant parts implemented for a particular
device. This class handles device detection.
'''

import os, subprocess, time, re, sys, glob, shutil
from itertools import repeat
from math import ceil

from calibre.devices.interface import DevicePlugin
from calibre.devices.errors import DeviceError
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre import iswindows, islinux, isosx, __appname__
from calibre.utils.filenames import ascii_filename as sanitize

class Device(DeviceConfig, DevicePlugin):
    '''
    This class provides logic common to all drivers for devices that export themselves
    as USB Mass Storage devices. If you are writing such a driver, inherit from this
    class.
    '''

    VENDOR_ID   = 0x0
    PRODUCT_ID  = 0x0
    BCD         = None

    VENDOR_NAME = None
    WINDOWS_MAIN_MEM = None
    WINDOWS_CARD_A_MEM = None
    WINDOWS_CARD_B_MEM = None

    # The following are used by the check_ioreg_line method and can be either:
    # None, a string, a list of strings or a compiled regular expression
    OSX_MAIN_MEM = None
    OSX_CARD_A_MEM = None
    OSX_CARD_B_MEM = None

    MAIN_MEMORY_VOLUME_LABEL  = ''
    STORAGE_CARD_VOLUME_LABEL = ''
    STORAGE_CARD2_VOLUME_LABEL = None

    SUPPORTS_SUB_DIRS = False
    MUST_READ_METADATA = False

    FDI_TEMPLATE = \
'''
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                %(BCD_start)s
                  <match key="@info.parent:storage.lun" int="%(lun0)d">
                          <merge key="volume.label" type="string">%(main_memory)s</merge>
                          <merge key="%(app)s.mainvolume" type="string">%(deviceclass)s</merge>
                  </match>
                %(BCD_end)s
              </match>
          </match>
      </match>
  </device>
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                %(BCD_start)s
                  <match key="@info.parent:storage.lun" int="%(lun1)d">
                          <merge key="volume.label" type="string">%(storage_card)s</merge>
                          <merge key="%(app)s.cardvolume" type="string">%(deviceclass)s</merge>
                  </match>
                %(BCD_end)s
              </match>
          </match>
      </match>
  </device>
  <device>
      <match key="info.category" string="volume">
          <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.vendor_id" int="%(vendor_id)s">
              <match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.product_id" int="%(product_id)s">
                %(BCD_start)s
                  <match key="@info.parent:storage.lun" int="%(lun2)d">
                          <merge key="volume.label" type="string">%(storage_card)s</merge>
                          <merge key="%(app)s.cardvolume" type="string">%(deviceclass)s</merge>
                  </match>
                %(BCD_end)s
              </match>
          </match>
      </match>
  </device>
'''
    FDI_LUNS = {'lun0':0, 'lun1':1, 'lun2':2}
    FDI_BCD_TEMPLATE = '<match key="@info.parent:@info.parent:@info.parent:@info.parent:usb.device_revision_bcd" int="%(bcd)s">'

    def reset(self, key='-1', log_packets=False, report_progress=None) :
        self._main_prefix = self._card_a_prefix = self._card_b_prefix = None

    @classmethod
    def get_fdi(cls):
        fdi = ''
        for vid in cls.VENDOR_ID:
            for pid in cls.PRODUCT_ID:
                fdi_base_values = dict(
                                       app=__appname__,
                                       deviceclass=cls.__name__,
                                       vendor_id=hex(vid),
                                       product_id=hex(pid),
                                       main_memory=cls.MAIN_MEMORY_VOLUME_LABEL,
                                       storage_card=cls.STORAGE_CARD_VOLUME_LABEL,
                                  )
                fdi_base_values.update(cls.FDI_LUNS)

                if cls.BCD is None:
                    fdi_base_values['BCD_start'] = ''
                    fdi_base_values['BCD_end'] = ''
                    fdi += cls.FDI_TEMPLATE % fdi_base_values
                else:
                    for bcd in cls.BCD:
                        fdi_bcd_values = fdi_base_values
                        fdi_bcd_values['BCD_start'] = cls.FDI_BCD_TEMPLATE % dict(bcd=hex(bcd))
                        fdi_bcd_values['BCD_end'] = '</match>'
                        fdi += cls.FDI_TEMPLATE % fdi_bcd_values

        return fdi

    def set_progress_reporter(self, report_progress):
        self.report_progress = report_progress

    def card_prefix(self, end_session=True):
        return (self._card_a_prefix, self._card_b_prefix)

    @classmethod
    def _windows_space(cls, prefix):
        if not prefix:
            return 0, 0
        win32file = __import__('win32file', globals(), locals(), [], -1)
        try:
            sectors_per_cluster, bytes_per_sector, free_clusters, total_clusters = \
                win32file.GetDiskFreeSpace(prefix[:-1])
        except Exception, err:
            if getattr(err, 'args', [None])[0] == 21: # Disk not ready
                time.sleep(3)
                sectors_per_cluster, bytes_per_sector, free_clusters, total_clusters = \
                    win32file.GetDiskFreeSpace(prefix[:-1])
            else: raise
        mult = sectors_per_cluster * bytes_per_sector
        return total_clusters * mult, free_clusters * mult

    def total_space(self, end_session=True):
        msz = casz = cbsz = 0
        if not iswindows:
            if self._main_prefix is not None:
                stats = os.statvfs(self._main_prefix)
                msz = stats.f_frsize * (stats.f_blocks + stats.f_bavail - stats.f_bfree)
            if self._card_a_prefix is not None:
                stats = os.statvfs(self._card_a_prefix)
                casz = stats.f_frsize * (stats.f_blocks + stats.f_bavail - stats.f_bfree)
            if self._card_b_prefix is not None:
                stats = os.statvfs(self._card_b_prefix)
                cbsz = stats.f_frsize * (stats.f_blocks + stats.f_bavail - stats.f_bfree)
        else:
            msz = self._windows_space(self._main_prefix)[0]
            casz = self._windows_space(self._card_a_prefix)[0]
            cbsz = self._windows_space(self._card_b_prefix)[0]

        return (msz, casz, cbsz)

    def free_space(self, end_session=True):
        msz = casz = cbsz = 0
        if not iswindows:
            if self._main_prefix is not None:
                stats = os.statvfs(self._main_prefix)
                msz = stats.f_frsize * stats.f_bavail
            if self._card_a_prefix is not None:
                stats = os.statvfs(self._card_a_prefix)
                casz = stats.f_frsize * stats.f_bavail
            if self._card_b_prefix is not None:
                stats = os.statvfs(self._card_b_prefix)
                cbsz = stats.f_frsize * stats.f_bavail
        else:
            msz = self._windows_space(self._main_prefix)[1]
            casz = self._windows_space(self._card_a_prefix)[1]
            cbsz = self._windows_space(self._card_b_prefix)[1]

        return (msz, casz, cbsz)

    def windows_match_device(self, drive, attr):
        pnp_id = str(drive.PNPDeviceID).upper()
        device_id = getattr(self, attr)
        if device_id is None or \
                'VEN_' + str(self.VENDOR_NAME).upper() not in pnp_id:
            return False

        if hasattr(device_id, 'search'):
            return device_id.search(pnp_id) is not None

        if isinstance(device_id, basestring):
            device_id = [device_id]

        for x in device_id:
            x = x.upper()

            if 'PROD_' + x in pnp_id:
                return True

        return False

    def windows_get_drive_prefix(self, drive):
        prefix = None

        try:
            partition = drive.associators("Win32_DiskDriveToDiskPartition")[0]
            logical_disk = partition.associators('Win32_LogicalDiskToPartition')[0]
            prefix = logical_disk.DeviceID + os.sep
        except IndexError:
            pass

        return prefix

    def windows_sort_drives(self, drives):
        '''
        Called to disambiguate main memory and storage card for devices that
        do not distinguish between them on the basis of `WINDOWS_CARD_NAME`.
        For e.g.: The EB600
        '''
        return drives

    def open_windows(self):

        def matches_q(drive, attr):
            q = getattr(self, attr)
            if q is None: return False
            if isinstance(q, basestring):
                q = [q]
            pnp = str(drive.PNPDeviceID)
            for x in q:
                if x in pnp:
                    return True
            return False


        time.sleep(6)
        drives = {}
        wmi = __import__('wmi', globals(), locals(), [], -1)
        c = wmi.WMI(find_classes=False)
        for drive in c.Win32_DiskDrive():
            if self.windows_match_device(drive, 'WINDOWS_CARD_A_MEM') and not drives.get('carda', None):
                drives['carda'] = self.windows_get_drive_prefix(drive)
            elif self.windows_match_device(drive, 'WINDOWS_CARD_B_MEM') and not drives.get('cardb', None):
                drives['cardb'] = self.windows_get_drive_prefix(drive)
            elif self.windows_match_device(drive, 'WINDOWS_MAIN_MEM') and not drives.get('main', None):
                drives['main'] = self.windows_get_drive_prefix(drive)

            if 'main' in drives.keys() and 'carda' in drives.keys() and \
                    'cardb' in drives.keys():
                break

        if 'main' not in drives:
            raise DeviceError(
                _('Unable to detect the %s disk drive. Try rebooting.') %
                self.__class__.__name__)

        drives = self.windows_sort_drives(drives)
        self._main_prefix = drives.get('main')
        self._card_a_prefix = drives.get('carda', None)
        self._card_b_prefix = drives.get('cardb', None)

    @classmethod
    def run_ioreg(cls, raw=None):
        if raw is not None:
            return raw
        ioreg = '/usr/sbin/ioreg'
        if not os.access(ioreg, os.X_OK):
            ioreg = 'ioreg'
        return subprocess.Popen((ioreg+' -w 0 -S -c IOMedia').split(),
                                stdout=subprocess.PIPE).communicate()[0]

    def osx_sort_names(self, names):
        return names

    def check_ioreg_line(self, line, pat):
        if pat is None:
            return False
        if not line.strip().endswith('<class IOMedia>'):
            return False
        if hasattr(pat, 'search'):
            return pat.search(line) is not None
        if isinstance(pat, basestring):
            pat = [pat]
        for x in pat:
            if x in line:
                return True
        return False


    def get_osx_mountpoints(self, raw=None):
        raw = self.run_ioreg(raw)
        lines = raw.splitlines()
        names = {}

        def get_dev_node(lines, loc):
            for line in lines:
                line = line.strip()
                if line.endswith('}'):
                    break
                match = re.search(r'"BSD Name"\s+=\s+"(.*?)"', line)
                if match is not None:
                    names[loc] = match.group(1)
                    break

        for i, line in enumerate(lines):
            if 'main' not in names and self.check_ioreg_line(line, self.OSX_MAIN_MEM):
                get_dev_node(lines[i+1:], 'main')
            if 'carda' not in names and self.check_ioreg_line(line, self.OSX_CARD_A_MEM):
                get_dev_node(lines[i+1:], 'carda')
            if 'cardb' not in names and self.check_ioreg_line(line, self.OSX_CARD_B_MEM):
                get_dev_node(lines[i+1:], 'cardb')
            if len(names.keys()) == 3:
                break
        return self.osx_sort_names(names)

    def open_osx(self):
        mount = subprocess.Popen('mount', shell=True,  stdout=subprocess.PIPE).stdout.read()
        names = self.get_osx_mountpoints()
        dev_pat = r'/dev/%s(\w*)\s+on\s+([^\(]+)\s+'
        if 'main' not in names.keys():
            raise DeviceError(_('Unable to detect the %s disk drive. Try rebooting.')%self.__class__.__name__)
        main_pat = dev_pat % names['main']
        self._main_prefix = re.search(main_pat, mount).group(2) + os.sep
        card_a_pat = names['carda'] if 'carda' in names.keys() else None
        card_b_pat = names['cardb'] if 'cardb' in names.keys() else None

        def get_card_prefix(pat):
            if pat is not None:
                pat = dev_pat % pat
                return re.search(pat, mount).group(2) + os.sep
            else:
                return None

        self._card_a_prefix = get_card_prefix(card_a_pat)
        self._card_b_prefix = get_card_prefix(card_b_pat)

    def find_device_nodes(self):

        def walk(base):
            base = os.path.abspath(os.path.realpath(base))
            for x in os.listdir(base):
                p = os.path.join(base, x)
                if os.path.islink(p) or not os.access(p, os.R_OK):
                    continue
                isfile = os.path.isfile(p)
                yield p, isfile
                if not isfile:
                    for y, q in walk(p):
                        yield y, q

        def raw2num(raw):
            raw = raw.lower()
            if not raw.startswith('0x'):
                raw = '0x' + raw
            return int(raw, 16)

        # Find device node based on vendor, product and bcd
        d, j = os.path.dirname, os.path.join
        usb_dir = None

        def test(val, attr):
            q = getattr(self, attr)
            if q is None: return True
            return q == val or val in q

        for x, isfile in walk('/sys/devices'):
            if isfile and x.endswith('idVendor'):
                usb_dir = d(x)
                for y in ('idProduct',):
                    if not os.access(j(usb_dir, y), os.R_OK):
                        usb_dir = None
                        continue
                e = lambda q : raw2num(open(j(usb_dir, q)).read())
                ven, prod = map(e, ('idVendor', 'idProduct'))
                if not (test(ven, 'VENDOR_ID') and test(prod, 'PRODUCT_ID')):
                    usb_dir = None
                    continue
                if self.BCD is not None:
                    if not os.access(j(usb_dir, 'bcdDevice'), os.R_OK) or \
                            not test(e('bcdDevice'), 'BCD'):
                        usb_dir = None
                        continue
                    else:
                        break
                else:
                    break

        if usb_dir is None:
            raise DeviceError(_('Unable to detect the %s disk drive.')
                    %self.__class__.__name__)

        devnodes, ok = [], {}
        for x, isfile in walk(usb_dir):
            if not isfile and '/block/' in x:
                parts = x.split('/')
                idx = parts.index('block')
                if idx == len(parts)-2:
                    sz = j(x, 'size')
                    node = parts[idx+1]
                    try:
                        exists = int(open(sz).read()) > 0
                        if exists:
                            node = self.find_largest_partition(x)
                            ok[node] = True
                        else:
                            ok[node] = False
                    except:
                        ok[node] = False
                    devnodes.append(node)

        devnodes += list(repeat(None, 3))
        ans = tuple(['/dev/'+x if ok.get(x, False) else None for x in devnodes[:3]])
        return self.linux_swap_drives(ans)

    def linux_swap_drives(self, drives):
        return drives

    def node_mountpoint(self, node):

        def de_mangle(raw):
            return raw.replace('\\040', ' ').replace('\\011', '\t').replace('\\012',
                    '\n').replace('\\0134', '\\')

        for line in open('/proc/mounts').readlines():
            line = line.split()
            if line[0] == node:
                return de_mangle(line[1])
        return None

    def find_largest_partition(self, path):
        node = path.split('/')[-1]
        nodes = []
        for x in glob.glob(path+'/'+node+'*'):
            sz = x + '/size'

            if not os.access(sz, os.R_OK):
                continue
            try:
                sz = int(open(sz).read())
            except:
                continue
            if sz > 0:
                nodes.append((x.split('/')[-1], sz))

        nodes.sort(cmp=lambda x, y: cmp(x[1], y[1]))
        if not nodes:
            return node
        return nodes[-1][0]


    def open_linux(self):

        def mount(node, type):
            mp = self.node_mountpoint(node)
            if mp is not None:
                return mp, 0
            if type == 'main':
                label = self.MAIN_MEMORY_VOLUME_LABEL
            if type == 'carda':
                label = self.STORAGE_CARD_VOLUME_LABEL
            if type == 'cardb':
                label = self.STORAGE_CARD2_VOLUME_LABEL
                if label is None:
                    label = self.STORAGE_CARD_VOLUME_LABEL + ' 2'
            extra = 0
            while True:
                q = ' (%d)'%extra if extra else ''
                if not os.path.exists('/media/'+label+q):
                    break
                extra += 1
            if extra:
                label += ' (%d)'%extra

            def do_mount(node, label):
                cmd = ['pmount', '-w', '-s']
                try:
                    p = subprocess.Popen(cmd + [node, label])
                except OSError:
                    raise DeviceError(_('You must install the pmount package.'))
                while p.poll() is None:
                    time.sleep(0.1)
                return p.returncode

            ret = do_mount(node, label)
            if ret != 0:
                return None, ret
            return self.node_mountpoint(node)+'/', 0


        main, carda, cardb = self.find_device_nodes()
        if main is None:
            raise DeviceError(_('Unable to detect the %s disk drive.')
                    %self.__class__.__name__)

        mp, ret = mount(main, 'main')
        if mp is None:
            raise DeviceError(
            _('Unable to mount main memory (Error code: %d)')%ret)
        if not mp.endswith('/'): mp += '/'
        self._main_prefix = mp
        cards = [(carda, '_card_a_prefix', 'carda'),
                 (cardb, '_card_b_prefix', 'cardb')]
        for card, prefix, typ in cards:
            if card is None: continue
            mp, ret = mount(card, typ)
            if mp is None:
                print >>sys.stderr, 'Unable to mount card (Error code: %d)'%ret
            else:
                if not mp.endswith('/'): mp += '/'
                setattr(self, prefix, mp)

    def open(self):
        time.sleep(5)
        self._main_prefix = self._card_a_prefix = self._card_b_prefix = None
        if islinux:
            try:
                self.open_linux()
            except DeviceError:
                time.sleep(7)
                self.open_linux()
        if iswindows:
            try:
                self.open_windows()
            except DeviceError:
                time.sleep(3)
                self.open_windows()
        if isosx:
            try:
                self.open_osx()
            except DeviceError:
                time.sleep(3)
                self.open_osx()

    def eject_windows(self):
        from calibre.constants import plugins
        from threading import Thread
        winutil, winutil_err = plugins['winutil']
        drives = []
        for x in ('_main_prefix', '_card_a_prefix', '_card_b_prefix'):
            x = getattr(self, x, None)
            if x is not None:
                drives.append(x[0].upper())

        def do_it(drives):
            for d in drives:
                try:
                    winutil.eject_drive(bytes(d)[0])
                except:
                    pass

        t = Thread(target=do_it, args=[drives])
        t.daemon = True
        t.start()
        self.__save_win_eject_thread = t

    def eject_osx(self):
        for x in ('_main_prefix', '_card_a_prefix', '_card_b_prefix'):
            x = getattr(self, x, None)
            if x is not None:
                try:
                    subprocess.Popen(['diskutil', 'eject', x])
                except:
                    pass

    def eject_linux(self):
        drives = self.find_device_nodes()
        success = False
        for drive in drives:
            if drive:
                cmd = ['pumount', '-l']
                try:
                    p = subprocess.Popen(cmd + [drive])
                except:
                    pass
                while p.poll() is None:
                    time.sleep(0.1)
                success = success or p.returncode == 0
                try:
                    subprocess.Popen(['sudo', 'eject', drive])
                except:
                    pass
        for x in ('_main_prefix', '_card_a_prefix', '_card_b_prefix'):
            x = getattr(self, x, None)
            if x is not None:
                if x.startswith('/media/') and os.path.exists(x) \
                        and not os.listdir(x):
                    try:
                        shutil.rmtree(x)
                    except:
                        pass


    def eject(self):
        if islinux:
            try:
                self.eject_linux()
            except:
                pass
        if iswindows:
            try:
                self.eject_windows()
            except:
                pass
        if isosx:
            try:
                self.eject_osx()
            except:
                pass
        self._main_prefix = self._card_a_prefix = self._card_b_prefix = None

    def create_upload_path(self, path, mdata, fname):
        resizable = []
        newpath = path
        if self.SUPPORTS_SUB_DIRS and self.settings().use_subdirs:

            if 'tags' in mdata.keys():
                for tag in mdata['tags']:
                    if tag.startswith(_('News')):
                        newpath = os.path.join(newpath, 'news')
                        c = sanitize(mdata.get('title', ''))
                        if c:
                            newpath = os.path.join(newpath, c)
                            resizable.append(c)
                        c = sanitize(mdata.get('timestamp', ''))
                        if c:
                            newpath = os.path.join(newpath, c)
                            resizable.append(c)
                        break
                    elif tag.startswith('/'):
                        for c in tag.split('/'):
                            c = sanitize(c)
                            if not c: continue
                            newpath = os.path.join(newpath, c)
                            resizable.append(c)
                        break

            if newpath == path:
                c = sanitize(mdata.get('authors', _('Unknown')))
                if c:
                    newpath = os.path.join(newpath, c)
                    resizable.append(c)
                c = sanitize(mdata.get('title', _('Unknown')))
                if c:
                    newpath = os.path.join(newpath, c)
                    resizable.append(c)

        newpath = os.path.abspath(newpath)
        fname = sanitize(fname)
        resizable.append(fname)

        filepath = os.path.join(newpath, fname)

        if len(filepath) > 245:
            extra = len(filepath) - 245
            delta = int(ceil(extra/float(len(resizable))))
            for x in resizable:
                if delta > len(x):
                    r = x[0] if x is resizable[-1] else ''
                else:
                    if x is resizable[-1]:
                        b, e = os.path.splitext(x)
                        r = b[:-delta]+e
                        if r.startswith('.'): r = x[0]+r
                    else:
                        r = x[:-delta]
                if x is resizable[-1]:
                    filepath = filepath.replace(os.sep+x, os.sep+r)
                else:
                    filepath = filepath.replace(os.sep+x+os.sep, os.sep+r+os.sep)
            filepath = filepath.replace(os.sep+os.sep, os.sep)
            newpath = os.path.dirname(filepath)


        if not os.path.exists(newpath):
            os.makedirs(newpath)

        return filepath


