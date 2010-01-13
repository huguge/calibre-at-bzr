# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Bookeen's Cybook Gen 3 and Opus
'''

import os
import re

from calibre.constants import isunix
from calibre.devices.usbms.driver import USBMS
import calibre.devices.cybook.t2b as t2b

class CYBOOK(USBMS):

    name           = 'Cybook Gen 3 / Opus Device Interface'
    gui_name       = 'Cybook Gen 3 / Opus'
    description    = _('Communicate with the Cybook Gen 3 / Opus eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['epub', 'mobi', 'prc', 'html', 'pdf', 'rtf', 'txt']

    VENDOR_ID   = [0x0bda, 0x3034]
    PRODUCT_ID  = [0x0703, 0x1795]
    BCD         = [0x110, 0x132]

    VENDOR_NAME = 'BOOKEEN'
    WINDOWS_MAIN_MEM = re.compile(r'CYBOOK_(OPUS|GEN3)__-FD')
    WINDOWS_CARD_A_MEM = re.compile('CYBOOK_(OPUS|GEN3)__-SD')
    OSX_MAIN_MEM_VOL_PAT = re.compile(r'/Cybook')

    EBOOK_DIR_MAIN = 'eBooks'
    EBOOK_DIR_CARD_A = 'eBooks'
    THUMBNAIL_HEIGHT = 144
    DELETE_EXTS = ['.mbp', '.dat', '.bin', '_6090.t2b', '.thn']
    SUPPORTS_SUB_DIRS = True

    def upload_cover(self, path, filename, metadata):
        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata and coverdata[2]:
            coverdata = coverdata[2]
        else:
            coverdata = None
        with open('%s_6090.t2b' % os.path.join(path, filename), 'wb') as t2bfile:
            t2b.write_t2b(t2bfile, coverdata)

    @classmethod
    def can_handle(cls, device_info, debug=False):
        if isunix:
            return device_info[3] == 'Bookeen' and (device_info[4] == 'Cybook Gen3' or device_info[4] == 'Cybook Opus')
        return True
