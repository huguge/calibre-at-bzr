# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Barns and Nobel's Nook
'''

import os

import cStringIO

from calibre.devices.usbms.driver import USBMS

class NOOK(USBMS):

    name           = 'Nook Device Interface'
    gui_name       = _('The Nook')
    description    = _('Communicate with the Nook eBook reader.')
    author         = 'John Schember'
    icon           = I('devices/nook.jpg')
    supported_platforms = ['windows', 'linux', 'osx']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdb', 'pdf']

    VENDOR_ID   = [0x2080]
    PRODUCT_ID  = [0x001]
    BCD         = [0x322]

    VENDOR_NAME = 'B&N'
    WINDOWS_MAIN_MEM = 'NOOK'
    WINDOWS_CARD_A_MEM = 'NOOK'

    OSX_MAIN_MEM = 'B&N nook Media'
    OSX_CARD_A_MEM = OSX_MAIN_MEM

    MAIN_MEMORY_VOLUME_LABEL  = 'Nook Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Nook Storage Card'

    EBOOK_DIR_MAIN = 'my documents'
    THUMBNAIL_HEIGHT = 144
    DELETE_EXTS = ['.jpg']
    SUPPORTS_SUB_DIRS = True

    def upload_cover(self, path, filename, metadata):
        try:
            from PIL import Image, ImageDraw
            Image, ImageDraw
        except ImportError:
            import Image, ImageDraw


        coverdata = metadata.get('cover', None)
        if coverdata:
            cover = Image.open(cStringIO.StringIO(coverdata[2]))
        else:
            coverdata = open(I('library.png'), 'rb').read()

            cover = Image.new('RGB', (96, 144), 'black')
            im = Image.open(cStringIO.StringIO(coverdata))
            im.thumbnail((96, 144), Image.ANTIALIAS)

            x, y = im.size
            cover.paste(im, ((96-x)/2, (144-y)/2))

            draw = ImageDraw.Draw(cover)
            draw.text((1, 15), metadata.get('title', _('Unknown')).encode('ascii', 'ignore'))
            draw.text((1, 115), metadata.get('authors', _('Unknown')).encode('ascii', 'ignore'))

        data = cStringIO.StringIO()
        cover.save(data, 'JPEG')
        coverdata = data.getvalue()

        with open('%s.jpg' % os.path.join(path, filename), 'wb') as coverfile:
            coverfile.write(coverdata)

    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives


