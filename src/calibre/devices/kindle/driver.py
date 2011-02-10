# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Amazon's Kindle
'''

import datetime, os, re, sys, json, hashlib

from calibre.devices.kindle.apnx import APNXBuilder
from calibre.devices.kindle.bookmark import Bookmark
from calibre.devices.usbms.driver import USBMS
from calibre.ebooks.oeb.base import OPF

'''
Notes on collections:

A collections cache is stored at system/collections.json
The cache is read only, changes made to it are overwritten (it is regenerated)
on device disconnect

A log of collection creation/manipulation is available at
system/userannotationlog

collections.json refers to books via a SHA1 hash of the absolute path to the
book (prefix is /mnt/us on my Kindle). The SHA1 hash may or may not be prefixed
by some characters, use the last 40 characters. For books from Amazon, the ASIN
is used instead.

Changing the metadata and resending the file doesn't seem to affect collections

Adding a book to a collection on the Kindle does not change the book file at all
(i.e. it is binary identical). Therefore collection information is not stored in
file metadata.
'''

class KINDLE(USBMS):

    name           = 'Kindle Device Interface'
    gui_name       = 'Amazon Kindle'
    icon           = I('devices/kindle.jpg')
    description    = _('Communicate with the Kindle eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['azw', 'mobi', 'prc', 'azw1', 'tpz', 'txt']

    VENDOR_ID   = [0x1949]
    PRODUCT_ID  = [0x0001]
    BCD         = [0x399]

    VENDOR_NAME = 'KINDLE'
    WINDOWS_MAIN_MEM = 'INTERNAL_STORAGE'
    WINDOWS_CARD_A_MEM = 'CARD_STORAGE'

    OSX_MAIN_MEM = 'Kindle Internal Storage Media'
    OSX_CARD_A_MEM = 'Kindle Card Storage Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Kindle Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Kindle Storage Card'

    EBOOK_DIR_MAIN = 'documents'
    EBOOK_DIR_CARD_A = 'documents'
    DELETE_EXTS = ['.mbp','.tan','.pdr']
    SUPPORTS_SUB_DIRS = True
    SUPPORTS_ANNOTATIONS = True

    WIRELESS_FILE_NAME_PATTERN = re.compile(
    r'(?P<title>[^-]+)-asin_(?P<asin>[a-zA-Z\d]{10,})-type_(?P<type>\w{4})-v_(?P<index>\d+).*')

    @classmethod
    def metadata_from_path(cls, path):
        mi = cls.metadata_from_formats([path])
        if mi.title == _('Unknown') or ('-asin' in mi.title and '-type' in mi.title):
            match = cls.WIRELESS_FILE_NAME_PATTERN.match(os.path.basename(path))
            if match is not None:
                mi.title = match.group('title')
                if not isinstance(mi.title, unicode):
                    mi.title = mi.title.decode(sys.getfilesystemencoding(),
                                               'replace')
        return mi


    def get_annotations(self, path_map):
        MBP_FORMATS = [u'azw', u'mobi', u'prc', u'txt']
        mbp_formats = set(MBP_FORMATS)
        PDR_FORMATS = [u'pdf']
        pdr_formats = set(PDR_FORMATS)
        TAN_FORMATS = [u'tpz', u'azw1']
        tan_formats = set(TAN_FORMATS)

        def get_storage():
            storage = []
            if self._main_prefix:
                storage.append(os.path.join(self._main_prefix, self.EBOOK_DIR_MAIN))
            if self._card_a_prefix:
                storage.append(os.path.join(self._card_a_prefix, self.EBOOK_DIR_CARD_A))
            if self._card_b_prefix:
                storage.append(os.path.join(self._card_b_prefix, self.EBOOK_DIR_CARD_B))
            return storage

        def resolve_bookmark_paths(storage, path_map):
            pop_list = []
            book_ext = {}
            for id in path_map:
                file_fmts = set()
                for fmt in path_map[id]['fmts']:
                    file_fmts.add(fmt)
                bookmark_extension = None
                if file_fmts.intersection(mbp_formats):
                    book_extension = list(file_fmts.intersection(mbp_formats))[0]
                    bookmark_extension = 'mbp'
                elif file_fmts.intersection(tan_formats):
                    book_extension = list(file_fmts.intersection(tan_formats))[0]
                    bookmark_extension = 'tan'
                elif file_fmts.intersection(pdr_formats):
                    book_extension = list(file_fmts.intersection(pdr_formats))[0]
                    bookmark_extension = 'pdr'

                if bookmark_extension:
                    for vol in storage:
                        bkmk_path = path_map[id]['path'].replace(os.path.abspath('/<storage>'),vol)
                        bkmk_path = bkmk_path.replace('bookmark',bookmark_extension)
                        if os.path.exists(bkmk_path):
                            path_map[id] = bkmk_path
                            book_ext[id] = book_extension
                            break
                    else:
                        pop_list.append(id)
                else:
                    pop_list.append(id)

            # Remove non-existent bookmark templates
            for id in pop_list:
                path_map.pop(id)
            return path_map, book_ext

        def get_my_clippings(storage, bookmarked_books):
            # add an entry for 'My Clippings.txt'
            for vol in storage:
                mc_path = os.path.join(vol,'My Clippings.txt')
                if os.path.exists(mc_path):
                    return mc_path
            return None

        storage = get_storage()
        path_map, book_ext = resolve_bookmark_paths(storage, path_map)

        bookmarked_books = {}
        for id in path_map:
            bookmark_ext = path_map[id].rpartition('.')[2]
            myBookmark = Bookmark(path_map[id], id, book_ext[id], bookmark_ext)
            bookmarked_books[id] = self.UserAnnotation(type='kindle_bookmark', value=myBookmark)

        mc_path = get_my_clippings(storage, bookmarked_books)
        if mc_path:
            timestamp = datetime.datetime.utcfromtimestamp(os.path.getmtime(mc_path))
            bookmarked_books['clippings'] = self.UserAnnotation(type='kindle_clippings',
                                              value=dict(path=mc_path,timestamp=timestamp))

        # This returns as job.result in gui2.ui.annotations_fetched(self,job)
        return bookmarked_books


class KINDLE2(KINDLE):

    name           = 'Kindle 2/3 Device Interface'
    description    = _('Communicate with the Kindle 2/3 eBook reader.')

    FORMATS        = KINDLE.FORMATS + ['pdf']
    DELETE_EXTS    = KINDLE.DELETE_EXTS + ['.apnx']
    
    PRODUCT_ID = [0x0002, 0x0004]
    BCD        = [0x0100]

    def books(self, oncard=None, end_session=True):
        bl = USBMS.books(self, oncard=oncard, end_session=end_session)
        # Read collections information
        collections = os.path.join(self._main_prefix, 'system', 'collections.json')
        if os.access(collections, os.R_OK):
            try:
                self.kindle_update_booklist(bl, collections)
            except:
                import traceback
                traceback.print_exc()
        return bl

    def kindle_update_booklist(self, bl, collections):
        with open(collections, 'rb') as f:
            collections = f.read()
        collections = json.loads(collections)
        path_map = {}
        for name, val in collections.items():
            col = name.split('@')[0]
            items = val.get('items', [])
            for x in items:
                x = x[-40:]
                if x not in path_map:
                    path_map[x] = set([])
                path_map[x].add(col)
        if path_map:
            for book in bl:
                path = '/mnt/us/'+book.lpath
                h = hashlib.sha1(path).hexdigest()
                if h in path_map:
                    book.device_collections = list(sorted(path_map[h]))
                    
    def upload_cover(self, path, filename, metadata, filepath):
        '''
        Hijacking this function to write the apnx file.
        '''
        if not filepath.lower().endswith('.mobi'):
            return

        apnx_path = '%s.apnx' % os.path.join(path, filename)
        apnx_builder = APNXBuilder()
        apnx_builder.write_apnx(filepath, apnx_path)
        

class KINDLE_DX(KINDLE2):

    name           = 'Kindle DX Device Interface'
    description    = _('Communicate with the Kindle DX eBook reader.')


    PRODUCT_ID = [0x0003]
    BCD        = [0x0100]

