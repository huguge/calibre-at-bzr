# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Bookeen's Cybook Gen 3
'''

from calibre.devices.usbms.driver import USBMS

class SNE(USBMS):

    name           = 'Samsung SNE Device Interface'
    gui_name       = 'Samsung SNE'
    description    = _('Communicate with the Samsung SNE eBook reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['epub', 'txt']

    VENDOR_ID   = [0x04e8]
    PRODUCT_ID  = [0x2051]
    BCD         = [0x0323]

    VENDOR_NAME = ''
    #WINDOWS_MAIN_MEM = 'MASS_STORAGE'
    #WINDOWS_CARD_A_MEM = 'MASS_STORAGE'

    MAIN_MEMORY_VOLUME_LABEL  = 'SNE Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'SNE Storage Card'

    EBOOK_DIR_MAIN = 'Book'
    SUPPORTS_SUB_DIRS = True


