'''
Created on 15 May 2010

@author: charles
'''
import os

from calibre.devices.usbms.driver import USBMS, BookList

# This class is added to the standard device plugin chain, so that it can
# be configured. It has invalid vendor_id etc, so it will never match a
# device. The 'real' FOLDER_DEVICE will use the config from it.
class FOLDER_DEVICE_FOR_CONFIG(USBMS):
    name           = 'Folder Device Interface'
    gui_name       = 'Folder Device'
    description    = _('Use an arbitrary folder as a device.')
    author         = 'John Schember/Charles Haley'
    supported_platforms = ['windows', 'osx', 'linux']
    FORMATS     = ['epub', 'fb2', 'mobi', 'lrf', 'tcr', 'pmlz', 'lit', 'rtf', 'rb', 'pdf', 'oeb', 'txt', 'pdb']
    VENDOR_ID   = 0xffff
    PRODUCT_ID  = 0xffff
    BCD         = 0xffff


class FOLDER_DEVICE(USBMS):
    type = _('Device Interface')

    name           = 'Folder Device Interface'
    gui_name       = 'Folder Device'
    description    = _('Use an arbitrary folder as a device.')
    author         = 'John Schember/Charles Haley'
    supported_platforms = ['windows', 'osx', 'linux']
    FORMATS     = ['epub', 'fb2', 'mobi', 'lrf', 'tcr', 'pmlz', 'lit', 'rtf', 'rb', 'pdf', 'oeb', 'txt', 'pdb']

    VENDOR_ID   = 0xffff
    PRODUCT_ID  = 0xffff
    BCD         = 0xffff

    THUMBNAIL_HEIGHT = 68 # Height for thumbnails on device

    CAN_SET_METADATA = True
    SUPPORTS_SUB_DIRS = True

    #: Icon for this device
    icon = I('devices/folder.svg')
    METADATA_CACHE = '.metadata.calibre'

    _main_prefix = ''
    _card_a_prefix = None
    _card_b_prefix = None

    is_connected = False

    def __init__(self, path):
        if not os.path.isdir(path):
            raise IOError, 'Path is not a folder'
        path = USBMS.normalize_path(path)
        if path.endswith(os.sep):
            self._main_prefix = path
        else:
            self._main_prefix = path + os.sep
        self.booklist_class = BookList
        self.is_connected = True

    def reset(self, key='-1', log_packets=False, report_progress=None,
              detected_device=None):
        pass

    def unmount_device(self):
        self._main_prefix = ''
        self.is_connected = False

    def is_usb_connected(self, devices_on_system, debug=False,
            only_presence=False):
        return self.is_connected, self

    def open(self):
        if not self._main_prefix:
            return False
        return True

    def set_progress_reporter(self, report_progress):
        self.report_progress = report_progress

    def card_prefix(self, end_session=True):
        return (None, None)

    def eject(self):
        self.is_connected = False

    @classmethod
    def settings(self):
        return FOLDER_DEVICE_FOR_CONFIG._config().parse()
