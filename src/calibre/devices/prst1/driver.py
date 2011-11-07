#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the SONY T1 devices
'''

import os, time, re
import sqlite3 as sqlite
from contextlib import closing
from datetime import date

from calibre.devices.usbms.driver import USBMS, debug_print
from calibre.devices.usbms.device import USBDevice
from calibre.devices.usbms.books import CollectionsBookList
from calibre.devices.usbms.books import BookList
from calibre.ebooks.metadata import authors_to_sort_string, authors_to_string
from calibre.constants import islinux

DBPATH = 'Sony_Reader/database/books.db'
THUMBPATH = 'Sony_Reader/database/cache/books/%s/thumbnail/main_thumbnail.jpg'

class ImageWrapper(object):
    def __init__(self, image_path):
        self.image_path = image_path

class PRST1(USBMS):
    name           = 'SONY PRST1 and newer Device Interface'
    gui_name       = 'SONY Reader'
    description    = _('Communicate with the PRST1 and newer SONY eBook readers')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']
    path_sep = '/'
    booklist_class = CollectionsBookList

    FORMATS      = ['epub', 'pdf', 'txt', 'book', 'zbf'] # The last two are
                                                         # used in japan
    CAN_SET_METADATA = ['collections']
    CAN_DO_DEVICE_DB_PLUGBOARD = True

    VENDOR_ID    = [0x054c]   #: SONY Vendor Id
    PRODUCT_ID   = [0x05c2]
    BCD          = [0x226]

    VENDOR_NAME        = 'SONY'
    WINDOWS_MAIN_MEM   = re.compile(
            r'(PRS-T1&)'
            )
    WINDOWS_CARD_A_MEM = re.compile(
            r'(PRS-T1__SD&)'
            )
    MAIN_MEMORY_VOLUME_LABEL = 'SONY Reader Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'SONY Reader Storage Card'

    THUMBNAIL_HEIGHT = 144
    SUPPORTS_SUB_DIRS = True
    SUPPORTS_USE_AUTHOR_SORT = True
    MUST_READ_METADATA = True
    EBOOK_DIR_MAIN   = 'Sony_Reader/media/books'

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('Comma separated list of metadata fields '
            'to turn into collections on the device. Possibilities include: ')+\
                    'series, tags, authors',
        _('Upload separate cover thumbnails for books') +
             ':::'+_('Normally, the SONY readers get the cover image from the'
             ' ebook file itself. With this option, calibre will send a '
             'separate cover image to the reader, useful if you are '
             'sending DRMed books in which you cannot change the cover.'),
        _('Refresh separate covers when using automatic management') +
             ':::' +
              _('Set this option to have separate book covers uploaded '
                'every time you connect your device. Unset this option if '
                'you have so many books on the reader that performance is '
                'unacceptable.'),
        _('Preserve cover aspect ratio when building thumbnails') +
              ':::' +
              _('Set this option if you want the cover thumbnails to have '
                'the same aspect ratio (width to height) as the cover. '
                'Unset it if you want the thumbnail to be the maximum size, '
                'ignoring aspect ratio.'),
        _('Use SONY Author Format (First Author Only)') +
              ':::' +
              _('Set this option if you want the author on the Sony to '
                'appear the same way the T1 sets it. This means it will '
                'only show the first author for books with multiple authors. '
                'Leave this disabled if you use Metadata Plugboards.')
    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
                ', '.join(['series', 'tags']),
                True,
                False,
                True,
                False,
    ]

    OPT_COLLECTIONS    = 0
    OPT_UPLOAD_COVERS  = 1
    OPT_REFRESH_COVERS = 2
    OPT_PRESERVE_ASPECT_RATIO = 3
    OPT_USE_SONY_AUTHORS = 4

    plugboards = None
    plugboard_func = None

    def post_open_callback(self):
        # Set the thumbnail width to the theoretical max if the user has asked
        # that we do not preserve aspect ratio
        ec = self.settings().extra_customization
        if not ec[self.OPT_PRESERVE_ASPECT_RATIO]:
            self.THUMBNAIL_WIDTH = 108
        self.WANTS_UPDATED_THUMBNAILS = ec[self.OPT_REFRESH_COVERS]
        # Make sure the date offset is set to none, we'll calculate it in books.
        self.device_offset = None

    def windows_filter_pnp_id(self, pnp_id):
        return '_LAUNCHER' in pnp_id or '_SETTING' in pnp_id

    def get_carda_ebook_dir(self, for_upload=False):
        if for_upload:
            return self.EBOOK_DIR_MAIN
        return self.EBOOK_DIR_CARD_A

    def get_main_ebook_dir(self, for_upload=False):
        if for_upload:
            return self.EBOOK_DIR_MAIN
        return ''

    def can_handle(self, devinfo, debug=False):
        if islinux:
            dev = USBDevice(devinfo)
            main, carda, cardb = self.find_device_nodes(detected_device=dev)
            if main is None and carda is None and cardb is None:
                if debug:
                    print ('\tPRS-T1: Appears to be in non data mode'
                            ' or was ejected, ignoring')
                return False
        return True

    def books(self, oncard=None, end_session=True):
        dummy_bl = BookList(None, None, None)

        if (
                (oncard == 'carda' and not self._card_a_prefix) or
                (oncard and oncard != 'carda')
            ):
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl

        prefix = self._card_a_prefix if oncard == 'carda' else self._main_prefix

        # Let parent driver get the books
        self.booklist_class.rebuild_collections = self.rebuild_collections
        bl = USBMS.books(self, oncard=oncard, end_session=end_session)

        dbpath = self.normalize_path(prefix + DBPATH)
        debug_print("SQLite DB Path: " + dbpath)

        with closing(sqlite.connect(dbpath)) as connection:
            # Replace undecodable characters in the db instead of erroring out
            connection.text_factory = lambda x: unicode(x, "utf-8", "replace")

            cursor = connection.cursor()
            # Query collections
            query = '''
                SELECT books._id, collection.title
                    FROM collections
                    LEFT OUTER JOIN books
                    LEFT OUTER JOIN collection
                    WHERE collections.content_id = books._id AND
                    collections.collection_id = collection._id
                '''
            cursor.execute(query)

            bl_collections = {}
            for i, row in enumerate(cursor):
                bl_collections.setdefault(row[0], [])
                bl_collections[row[0]].append(row[1])

            # collect information on offsets, but assume any
            # offset we already calculated is correct
            if self.device_offset is None:
                query = 'SELECT file_path, modified_date FROM books'
                cursor.execute(query)

                time_offsets = {}
                for i, row in enumerate(cursor):
                    comp_date = int(os.path.getmtime(self.normalize_path(prefix + row[0])) * 1000);
                    device_date = int(row[1]);
                    offset = device_date - comp_date
                    time_offsets.setdefault(offset, 0)
                    time_offsets[offset] = time_offsets[offset] + 1

                try:
                    device_offset = max(time_offsets,key = lambda a: time_offsets.get(a))
                    debug_print("Device Offset: %d ms"%device_offset)
                    self.device_offset = device_offset
                except ValueError:
                    debug_print("No Books To Detect Device Offset.")

            for idx, book in enumerate(bl):
                query = 'SELECT _id, thumbnail FROM books WHERE file_path = ?'
                t = (book.lpath,)
                cursor.execute (query, t)

                for i, row in enumerate(cursor):
                    book.device_collections = bl_collections.get(row[0], None)
                    thumbnail = row[1]
                    if thumbnail is not None:
                        thumbnail = self.normalize_path(prefix + thumbnail)
                        book.thumbnail = ImageWrapper(thumbnail)

            cursor.close()

        return bl

    def set_plugboards(self, plugboards, pb_func):
        self.plugboards = plugboards
        self.plugboard_func = pb_func

    def sync_booklists(self, booklists, end_session=True):
        debug_print('PRST1: starting sync_booklists')

        opts = self.settings()
        if opts.extra_customization:
            collections = [x.strip() for x in
                    opts.extra_customization[self.OPT_COLLECTIONS].split(',')]
        else:
            collections = []
        debug_print('PRST1: collection fields:', collections)

        if booklists[0] is not None:
            self.update_device_database(booklists[0], collections, None)
        if booklists[1] is not None:
            self.update_device_database(booklists[1], collections, 'carda')

        USBMS.sync_booklists(self, booklists, end_session=end_session)
        debug_print('PRST1: finished sync_booklists')

    def update_device_database(self, booklist, collections_attributes, oncard):
        debug_print('PRST1: starting update_device_database')

        plugboard = None
        if self.plugboard_func:
            plugboard = self.plugboard_func(self.__class__.__name__,
                    'device_db', self.plugboards)
            debug_print("PRST1: Using Plugboard", plugboard)

        prefix = self._card_a_prefix if oncard == 'carda' else self._main_prefix
        if prefix is None:
            # Reader has no sd card inserted
            return
        source_id = 1 if oncard == 'carda' else 0

        dbpath = self.normalize_path(prefix + DBPATH)
        debug_print("SQLite DB Path: " + dbpath)

        collections = booklist.get_collections(collections_attributes)

        with closing(sqlite.connect(dbpath)) as connection:
            self.update_device_books(connection, booklist, source_id, plugboard)
            self.update_device_collections(connection, booklist, collections, source_id)

        debug_print('PRST1: finished update_device_database')

    def update_device_books(self, connection, booklist, source_id, plugboard):
        opts = self.settings()
        upload_covers = opts.extra_customization[self.OPT_UPLOAD_COVERS]
        refresh_covers = opts.extra_customization[self.OPT_REFRESH_COVERS]
        use_sony_authors = opts.extra_customization[self.OPT_USE_SONY_AUTHORS]

        cursor = connection.cursor()

        # Get existing books
        query = 'SELECT file_path, _id FROM books'
        cursor.execute(query)

        db_books = {}
        for i, row in enumerate(cursor):
            lpath = row[0].replace('\\', '/')
            db_books[lpath] = row[1]

        for book in booklist:
            # Run through plugboard if needed
            if plugboard is not None:
                newmi = book.deepcopy_metadata()
                newmi.template_to_attribute(book, plugboard)
            else:
                newmi = book

            # Get Metadata We Want
            lpath = book.lpath
            try:
                if opts.use_author_sort:
                    if newmi.author_sort:
                        author = newmi.author_sort
                    else:
                        author = authors_to_sort_string(newmi.authors)
                else:
                    if use_sony_authors:
                        author = newmi.authors[0]
                    else:
                        author = authors_to_string(newmi.authors)
            except:
                author = _('Unknown')
            title = newmi.title or _('Unknown')

            # Get modified date
            modified_date = os.path.getmtime(book.path) * 1000
            if self.device_offset is not None:
                modified_date = modified_date + self.device_offset
            else:
                time_offset = -time.altzone if time.daylight else -time.timezone
                modified_date = modified_date + (time_offset * 1000)

            if lpath not in db_books:
                query = '''
                INSERT INTO books
                (title, author, source_id, added_date, modified_date,
                file_path, file_name, file_size, mime_type, corrupted,
                prevent_delete)
                values (?,?,?,?,?,?,?,?,?,0,0)
                '''
                t = (title, author, source_id, int(time.time() * 1000),
                        modified_date, lpath,
                        os.path.basename(lpath), book.size, book.mime)
                cursor.execute(query, t)
                book.bookId = cursor.lastrowid
                if upload_covers:
                    self.upload_book_cover(connection, book, source_id)
                debug_print('Inserted New Book: ' + book.title)
            else:
                query = '''
                UPDATE books
                SET title = ?, author = ?, modified_date = ?, file_size = ?
                WHERE file_path = ?
                '''
                t = (title, author, modified_date, book.size, lpath)
                cursor.execute(query, t)
                book.bookId = db_books[lpath]
                if refresh_covers:
                    self.upload_book_cover(connection, book, source_id)
                db_books[lpath] = None

            if self.is_sony_periodical(book):
                self.periodicalize_book(connection, book)

        for book, bookId in db_books.items():
            if bookId is not None:
                # Remove From Collections
                query = 'DELETE FROM collections WHERE content_id = ?'
                t = (bookId,)
                cursor.execute(query, t)
                # Remove from Books
                query = 'DELETE FROM books where _id = ?'
                t = (bookId,)
                cursor.execute(query, t)
                debug_print('Deleted Book:' + book)

        connection.commit()
        cursor.close()

    def update_device_collections(self, connection, booklist, collections,
            source_id):
        cursor = connection.cursor()

        if collections:
            # Get existing collections
            query = 'SELECT _id, title FROM collection'
            cursor.execute(query)

            db_collections = {}
            for i, row in enumerate(cursor):
                db_collections[row[1]] = row[0]

            for collection, books in collections.items():
                if collection not in db_collections:
                    query = 'INSERT INTO collection (title, source_id) VALUES (?,?)'
                    t = (collection, source_id)
                    cursor.execute(query, t)
                    db_collections[collection] = cursor.lastrowid
                    debug_print('Inserted New Collection: ' + collection)

                # Get existing books in collection
                query = '''
                SELECT books.file_path, content_id
                FROM collections
                LEFT OUTER JOIN books
                WHERE collection_id = ? AND books._id = collections.content_id
                '''
                t = (db_collections[collection],)
                cursor.execute(query, t)

                db_books = {}
                for i, row in enumerate(cursor):
                    db_books[row[0]] = row[1]

                for idx, book in enumerate(books):
                    if collection not in book.device_collections:
                        book.device_collections.append(collection)
                    if db_books.get(book.lpath, None) is None:
                        query = '''
                        INSERT INTO collections (collection_id, content_id,
                        added_order) values (?,?,?)
                        '''
                        t = (db_collections[collection], book.bookId, idx)
                        cursor.execute(query, t)
                        debug_print('Inserted Book Into Collection: ' +
                                book.title + ' -> ' + collection)
                    else:
                        query = '''
                        UPDATE collections
                        SET added_order = ?
                        WHERE content_id = ? AND collection_id = ?
                        '''
                        t = (idx, book.bookId, db_collections[collection])
                        cursor.execute(query, t)

                    db_books[book.lpath] = None

                for bookPath, bookId in db_books.items():
                    if bookId is not None:
                        query = ('DELETE FROM collections '
                                'WHERE content_id = ? AND collection_id = ? ')
                        t = (bookId, db_collections[collection],)
                        cursor.execute(query, t)
                        debug_print('Deleted Book From Collection: ' + bookPath
                                + ' -> ' + collection)

                db_collections[collection] = None

            for collection, collectionId in db_collections.items():
                if collectionId is not None:
                    # Remove Books from Collection
                    query = ('DELETE FROM collections '
                            'WHERE collection_id = ?')
                    t = (collectionId,)
                    cursor.execute(query, t)
                    # Remove Collection
                    query = ('DELETE FROM collection '
                            'WHERE _id = ?')
                    t = (collectionId,)
                    cursor.execute(query, t)
                    debug_print('Deleted Collection: ' + collection)


        connection.commit()
        cursor.close()

    def rebuild_collections(self, booklist, oncard):
        debug_print('PRST1: starting rebuild_collections')

        opts = self.settings()
        if opts.extra_customization:
            collections = [x.strip() for x in
                    opts.extra_customization[self.OPT_COLLECTIONS].split(',')]
        else:
            collections = []
        debug_print('PRST1: collection fields:', collections)

        self.update_device_database(booklist, collections, oncard)

        debug_print('PRS-T1: finished rebuild_collections')

    def upload_cover(self, path, filename, metadata, filepath):
        debug_print('PRS-T1: uploading cover')

        if filepath.startswith(self._main_prefix):
            prefix = self._main_prefix
            source_id = 0
        else:
            prefix = self._card_a_prefix
            source_id = 1

        metadata.lpath = filepath.partition(prefix)[2]
        metadata.lpath = metadata.lpath.replace('\\', '/')
        dbpath = self.normalize_path(prefix + DBPATH)
        debug_print("SQLite DB Path: " + dbpath)

        with closing(sqlite.connect(dbpath)) as connection:
            cursor = connection.cursor()

            query = 'SELECT _id FROM books WHERE file_path = ?'
            t = (metadata.lpath,)
            cursor.execute(query, t)

            for i, row in enumerate(cursor):
                metadata.bookId = row[0]

            cursor.close()

            if getattr(metadata, 'bookId', None) is not None:
                debug_print('PRS-T1: refreshing cover for book being sent')
                self.upload_book_cover(connection, metadata, source_id)

        debug_print('PRS-T1: done uploading cover')

    def upload_book_cover(self, connection, book, source_id):
        debug_print('PRST1: Uploading/Refreshing Cover for ' + book.title)
        if not book.thumbnail or not book.thumbnail[-1]:
            return
        cursor = connection.cursor()

        thumbnail_path = THUMBPATH%book.bookId

        prefix = self._main_prefix if source_id is 0 else self._card_a_prefix
        thumbnail_file_path = os.path.join(prefix, *thumbnail_path.split('/'))
        thumbnail_dir_path = os.path.dirname(thumbnail_file_path)
        if not os.path.exists(thumbnail_dir_path):
            os.makedirs(thumbnail_dir_path)

        with open(thumbnail_file_path, 'wb') as f:
            f.write(book.thumbnail[-1])

        query = 'UPDATE books SET thumbnail = ? WHERE _id = ?'
        t = (thumbnail_path, book.bookId,)
        cursor.execute(query, t)

        connection.commit()
        cursor.close()

    def is_sony_periodical(self, book):
        if _('News') not in book.tags:
            return False
        if not book.lpath.lower().endswith('.epub'):
            return False
        if book.pubdate.date() < date(2010, 10, 17):
            return False
        return True

    def periodicalize_book(self, connection, book):
        if not self.is_sony_periodical(book):
            return

        name = None
        if '[' in book.title:
            name = book.title.split('[')[0].strip()
            if len(name) < 4:
                name = None
        if not name:
            try:
                name = [t for t in book.tags if t != _('News')][0]
            except:
                name = None

        if not name:
            name = book.title

        pubdate = None
        try:
            pubdate = int(time.mktime(book.pubdate.timetuple()) * 1000)
        except:
            pass

        cursor = connection.cursor()

        periodical_schema = \
            "'http://xmlns.sony.net/e-book/prs/periodicals/1.0/newspaper/1.0'"
        # Setting this to the SONY periodical schema apparently causes errors
        # with some periodicals, therefore set it to null, since the special
        # periodical navigation doesn't work anyway.
        periodical_schema = 'null'

        query = '''
        UPDATE books
        SET conforms_to = %s,
            periodical_name = ?,
            description = ?,
            publication_date = ?
        WHERE _id = ?
        '''%periodical_schema
        t = (name, None, pubdate, book.bookId,)
        cursor.execute(query, t)

        connection.commit()
        cursor.close()
