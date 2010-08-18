from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
The database used to store ebook metadata
'''
import os, sys, shutil, cStringIO, glob, time, functools, traceback
from itertools import repeat
from math import floor

from PyQt4.QtGui import QImage

from calibre.ebooks.metadata import title_sort, author_to_author_sort
from calibre.library.database import LibraryDatabase
from calibre.library.field_metadata import FieldMetadata, TagsIcons
from calibre.library.schema_upgrades import SchemaUpgrade
from calibre.library.caches import ResultCache
from calibre.library.custom_columns import CustomColumns
from calibre.library.sqlite import connect, IntegrityError, DBThread
from calibre.library.prefs import DBPrefs
from calibre.ebooks.metadata import string_to_authors, authors_to_string, \
                                    MetaInformation
from calibre.ebooks.metadata.meta import get_metadata, metadata_from_formats
from calibre.constants import preferred_encoding, iswindows, isosx, filesystem_encoding
from calibre.ptempfile import PersistentTemporaryFile
from calibre.customize.ui import run_plugins_on_import
from calibre import isbytestring
from calibre.utils.filenames import ascii_filename
from calibre.utils.date import utcnow, now as nowf, utcfromtimestamp
from calibre.utils.config import prefs, tweaks
from calibre.utils.search_query_parser import saved_searches, set_saved_searches
from calibre.ebooks import BOOK_EXTENSIONS, check_ebook_format
from calibre.utils.magick.draw import save_cover_data_to

if iswindows:
    import calibre.utils.winshell as winshell

def delete_file(path):
    try:
        winshell.delete_file(path, silent=True, no_confirm=True)
    except:
        os.remove(path)

def delete_tree(path, permanent=False):
    if permanent:
        shutil.rmtree(path)
    else:
        try:
            if not permanent:
                winshell.delete_file(path, silent=True, no_confirm=True)
        except:
            shutil.rmtree(path)

copyfile = os.link if hasattr(os, 'link') else shutil.copyfile

class Tag(object):

    def __init__(self, name, id=None, count=0, state=0, avg=0, sort=None,
                 tooltip=None, icon=None):
        self.name = name
        self.id = id
        self.count = count
        self.state = state
        self.avg_rating = avg/2.0 if avg is not None else 0
        self.sort = sort
        if self.avg_rating > 0:
            if tooltip:
                tooltip = tooltip + ': '
            tooltip = _('%sAverage rating is %3.1f')%(tooltip, self.avg_rating)
        self.tooltip = tooltip
        self.icon = icon

    def __unicode__(self):
        return u'%s:%s:%s:%s:%s'%(self.name, self.count, self.id, self.state, self.tooltip)

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __repr__(self):
        return str(self)


class LibraryDatabase2(LibraryDatabase, SchemaUpgrade, CustomColumns):
    '''
    An ebook metadata database that stores references to ebook files on disk.
    '''
    PATH_LIMIT = 40 if 'win32' in sys.platform else 100

    @dynamic_property
    def user_version(self):
        doc = 'The user version of this database'

        def fget(self):
            return self.conn.get('pragma user_version;', all=False)

        def fset(self, val):
            self.conn.execute('pragma user_version=%d'%int(val))
            self.conn.commit()

        return property(doc=doc, fget=fget, fset=fset)

    def connect(self):
        if 'win32' in sys.platform and len(self.library_path) + 4*self.PATH_LIMIT + 10 > 259:
            raise ValueError('Path to library too long. Must be less than %d characters.'%(259-4*self.PATH_LIMIT-10))
        exists = os.path.exists(self.dbpath)
        self.conn = connect(self.dbpath, self.row_factory)
        if exists and self.user_version == 0:
            self.conn.close()
            os.remove(self.dbpath)
            self.conn = connect(self.dbpath, self.row_factory)
        if self.user_version == 0:
            self.initialize_database()
        # remember to add any filter to the connect method in sqlite.py as well
        # so that various code taht connects directly will not complain about
        # missing functions
        self.books_list_filter = self.conn.create_dynamic_filter('books_list_filter')
        # Store temporary tables in memory
        self.conn.execute('pragma temp_store=2')
        self.conn.commit()

    @classmethod
    def exists_at(cls, path):
        return path and os.path.exists(os.path.join(path, 'metadata.db'))

    def __init__(self, library_path, row_factory=False):
        self.field_metadata = FieldMetadata()
        if not os.path.exists(library_path):
            os.makedirs(library_path)
        self.listeners = set([])
        self.library_path = os.path.abspath(library_path)
        self.row_factory = row_factory
        self.dbpath = os.path.join(library_path, 'metadata.db')
        self.dbpath = os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH',
                self.dbpath)
        if isinstance(self.dbpath, unicode) and not iswindows:
            self.dbpath = self.dbpath.encode(filesystem_encoding)

        self.connect()
        self.is_case_sensitive = not iswindows and not isosx and \
            not os.path.exists(self.dbpath.replace('metadata.db', 'MeTAdAtA.dB'))
        SchemaUpgrade.__init__(self)
        self.initialize_dynamic()

    def initialize_dynamic(self):
        self.prefs = DBPrefs(self)

        # Migrate saved search and user categories to db preference scheme
        def migrate_preference(key, default):
            oldval = prefs[key]
            if oldval != default:
                self.prefs[key] = oldval
                prefs[key] = default
            if key not in self.prefs:
                self.prefs[key] = default

        migrate_preference('user_categories', {})
        migrate_preference('saved_searches', {})
        set_saved_searches(self, 'saved_searches')

        self.conn.executescript('''
        DROP TRIGGER IF EXISTS author_insert_trg;
        CREATE TEMP TRIGGER author_insert_trg
            AFTER INSERT ON authors
            BEGIN
            UPDATE authors SET sort=author_to_author_sort(NEW.name) WHERE id=NEW.id;
        END;
        DROP TRIGGER IF EXISTS author_update_trg;
        CREATE TEMP TRIGGER author_update_trg
            BEFORE UPDATE ON authors
            BEGIN
            UPDATE authors SET sort=author_to_author_sort(NEW.name)
            WHERE id=NEW.id AND name <> NEW.name;
        END;
        ''')
        self.conn.execute(
            'UPDATE authors SET sort=author_to_author_sort(name) WHERE sort IS NULL')
        self.conn.executescript(u'''
            CREATE TEMP VIEW IF NOT EXISTS tag_browser_news AS SELECT DISTINCT
                id,
                name,
                (SELECT COUNT(books_tags_link.id) FROM books_tags_link WHERE tag=x.id) count,
                (0) as avg_rating,
                name as sort
            FROM tags as x WHERE name!="{0}" AND id IN
                (SELECT DISTINCT tag FROM books_tags_link WHERE book IN
                    (SELECT DISTINCT book FROM books_tags_link WHERE tag IN
                        (SELECT id FROM tags WHERE name="{0}")));
            '''.format(_('News')))

        self.conn.executescript(u'''
            CREATE TEMP VIEW IF NOT EXISTS tag_browser_filtered_news AS SELECT DISTINCT
                id,
                name,
                (SELECT COUNT(books_tags_link.id) FROM books_tags_link WHERE tag=x.id and books_list_filter(book)) count,
                (0) as avg_rating,
                name as sort
            FROM tags as x WHERE name!="{0}" AND id IN
                (SELECT DISTINCT tag FROM books_tags_link WHERE book IN
                    (SELECT DISTINCT book FROM books_tags_link WHERE tag IN
                        (SELECT id FROM tags WHERE name="{0}")));
            '''.format(_('News')))
        self.conn.commit()


        CustomColumns.__init__(self)
        template = '''\
                (SELECT {query} FROM books_{table}_link AS link INNER JOIN
                    {table} ON(link.{link_col}={table}.id) WHERE link.book=books.id)
                    {col}
                '''
        columns = ['id', 'title',
            # col         table     link_col          query
            ('authors', 'authors', 'author', 'sortconcat(link.id, name)'),
             'timestamp',
             '(SELECT MAX(uncompressed_size) FROM data WHERE book=books.id) size',
            ('rating', 'ratings', 'rating', 'ratings.rating'),
            ('tags', 'tags', 'tag', 'group_concat(name)'),
             '(SELECT text FROM comments WHERE book=books.id) comments',
            ('series', 'series', 'series', 'name'),
            ('publisher', 'publishers', 'publisher', 'name'),
             'series_index',
             'sort',
             'author_sort',
             '(SELECT group_concat(format) FROM data WHERE data.book=books.id) formats',
             'isbn',
             'path',
             'lccn',
             'pubdate',
             'flags',
             'uuid'
            ]
        lines = []
        for col in columns:
            line = col
            if isinstance(col, tuple):
                line = template.format(col=col[0], table=col[1],
                        link_col=col[2], query=col[3])
            lines.append(line)

        custom_map = self.custom_columns_in_meta()
        # custom col labels are numbers (the id in the custom_columns table)
        custom_cols = list(sorted(custom_map.keys()))
        lines.extend([custom_map[x] for x in custom_cols])

        self.FIELD_MAP = {'id':0, 'title':1, 'authors':2, 'timestamp':3,
             'size':4, 'rating':5, 'tags':6, 'comments':7, 'series':8,
             'publisher':9, 'series_index':10,
             'sort':11, 'author_sort':12, 'formats':13, 'isbn':14, 'path':15,
             'lccn':16, 'pubdate':17, 'flags':18, 'uuid':19}

        for k,v in self.FIELD_MAP.iteritems():
            self.field_metadata.set_field_record_index(k, v, prefer_custom=False)

        base = max(self.FIELD_MAP.values())
        for col in custom_cols:
            self.FIELD_MAP[col] = base = base+1
            self.field_metadata.set_field_record_index(
                                        self.custom_column_num_map[col]['label'],
                                        base,
                                        prefer_custom=True)
            if self.custom_column_num_map[col]['datatype'] == 'series':
                # account for the series index column. Field_metadata knows that
                # the series index is one larger than the series. If you change
                # it here, be sure to change it there as well.
                self.FIELD_MAP[str(col)+'_s_index'] = base = base+1

        self.FIELD_MAP['cover'] = base+1
        self.field_metadata.set_field_record_index('cover', base+1, prefer_custom=False)
        self.FIELD_MAP['ondevice'] = base+2
        self.field_metadata.set_field_record_index('ondevice', base+2, prefer_custom=False)

        script = '''
        DROP VIEW IF EXISTS meta2;
        CREATE TEMP VIEW meta2 AS
        SELECT
        {0}
        FROM books;
        '''.format(', \n'.join(lines))
        self.conn.executescript(script)
        self.conn.commit()

        # Reconstruct the user categories, putting them into field_metadata
        # Assumption is that someone else will fix them if they change.
        tb_cats = self.field_metadata
        for k in tb_cats.keys():
            if tb_cats[k]['kind'] in ['user', 'search']:
                del tb_cats[k]
        for user_cat in sorted(self.prefs.get('user_categories', {}).keys()):
            cat_name = user_cat+':' # add the ':' to avoid name collision
            tb_cats.add_user_category(label=cat_name, name=user_cat)
        if len(saved_searches().names()):
            tb_cats.add_search_category(label='search', name=_('Searches'))

        self.book_on_device_func = None
        self.data    = ResultCache(self.FIELD_MAP, self.field_metadata)
        self.search  = self.data.search
        self.search_getting_ids  = self.data.search_getting_ids
        self.refresh = functools.partial(self.data.refresh, self)
        self.sort    = self.data.sort
        self.index   = self.data.index
        self.refresh_ids = functools.partial(self.data.refresh_ids, self)
        self.row     = self.data.row
        self.has_id  = self.data.has_id
        self.count   = self.data.count

        self.refresh_ondevice = functools.partial(self.data.refresh_ondevice, self)

        self.refresh()
        self.last_update_check = self.last_modified()


        def get_property(idx, index_is_id=False, loc=-1):
            row = self.data._data[idx] if index_is_id else self.data[idx]
            if row is not None:
                return row[loc]

        for prop in ('author_sort', 'authors', 'comment', 'comments', 'isbn',
                     'publisher', 'rating', 'series', 'series_index', 'tags',
                     'title', 'timestamp', 'uuid', 'pubdate'):
            setattr(self, prop, functools.partial(get_property,
                    loc=self.FIELD_MAP['comments' if prop == 'comment' else prop]))
        setattr(self, 'title_sort', functools.partial(get_property,
                loc=self.FIELD_MAP['sort']))

    def initialize_database(self):
        metadata_sqlite = open(P('metadata_sqlite.sql'), 'rb').read()
        self.conn.executescript(metadata_sqlite)
        self.user_version = 1

    def last_modified(self):
        ''' Return last modified time as a UTC datetime object'''
        return utcfromtimestamp(os.stat(self.dbpath).st_mtime)


    def check_if_modified(self):
        if self.last_modified() > self.last_update_check:
            self.refresh()
        self.last_update_check = utcnow()

    def path(self, index, index_is_id=False):
        'Return the relative path to the directory containing this books files as a unicode string.'
        row = self.data._data[index] if index_is_id else self.data[index]
        return row[self.FIELD_MAP['path']].replace('/', os.sep)


    def abspath(self, index, index_is_id=False):
        'Return the absolute path to the directory containing this books files as a unicode string.'
        path = os.path.join(self.library_path, self.path(index, index_is_id=index_is_id))
        if not os.path.exists(path):
            os.makedirs(path)
        return path


    def construct_path_name(self, id):
        '''
        Construct the directory name for this book based on its metadata.
        '''
        authors = self.authors(id, index_is_id=True)
        if not authors:
            authors = _('Unknown')
        author = ascii_filename(authors.split(',')[0][:self.PATH_LIMIT]).decode(filesystem_encoding, 'ignore')
        title  = ascii_filename(self.title(id, index_is_id=True)[:self.PATH_LIMIT]).decode(filesystem_encoding, 'ignore')
        path   = author + '/' + title + ' (%d)'%id
        return path

    def construct_file_name(self, id):
        '''
        Construct the file name for this book based on its metadata.
        '''
        authors = self.authors(id, index_is_id=True)
        if not authors:
            authors = _('Unknown')
        author = ascii_filename(authors.split(',')[0][:self.PATH_LIMIT]).decode(filesystem_encoding, 'replace')
        title  = ascii_filename(self.title(id, index_is_id=True)[:self.PATH_LIMIT]).decode(filesystem_encoding, 'replace')
        name   = title + ' - ' + author
        while name.endswith('.'):
            name = name[:-1]
        return name

    def rmtree(self, path, permanent=False):
        if not self.normpath(self.library_path).startswith(self.normpath(path)):
            delete_tree(path, permanent=permanent)

    def normpath(self, path):
        path = os.path.abspath(os.path.realpath(path))
        if not self.is_case_sensitive:
            path = path.lower()
        return path

    def set_path(self, index, index_is_id=False, commit=True):
        '''
        Set the path to the directory containing this books files based on its
        current title and author. If there was a previous directory, its contents
        are copied and it is deleted.
        '''
        id = index if  index_is_id else self.id(index)
        path = self.construct_path_name(id)
        current_path = self.path(id, index_is_id=True).replace(os.sep, '/')
        formats = self.formats(id, index_is_id=True)
        formats = formats.split(',') if formats else []
        # Check if the metadata used to construct paths has changed
        fname = self.construct_file_name(id)
        changed = False
        for format in formats:
            name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
            if name and name != fname:
                changed = True
                break
        if path == current_path and not changed:
            return

        tpath = os.path.join(self.library_path, *path.split('/'))
        if not os.path.exists(tpath):
            os.makedirs(tpath)
        spath = os.path.join(self.library_path, *current_path.split('/'))

        if current_path and os.path.exists(spath): # Migrate existing files
            cdata = self.cover(id, index_is_id=True)
            if cdata is not None:
                open(os.path.join(tpath, 'cover.jpg'), 'wb').write(cdata)
            for format in formats:
                # Get data as string (can't use file as source and target files may be the same)
                f = self.format(id, format, index_is_id=True, as_file=False)
                if not f:
                    continue
                stream = cStringIO.StringIO(f)
                self.add_format(id, format, stream, index_is_id=True, path=tpath)
        self.conn.execute('UPDATE books SET path=? WHERE id=?', (path, id))
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['path'], path, row_is_id=True)
        # Delete not needed directories
        if current_path and os.path.exists(spath):
            if self.normpath(spath) != self.normpath(tpath):
                self.rmtree(spath, permanent=True)
                parent = os.path.dirname(spath)
                if len(os.listdir(parent)) == 0:
                    self.rmtree(parent, permanent=True)
        curpath = self.library_path
        c1, c2 = current_path.split('/'), path.split('/')
        if not self.is_case_sensitive and len(c1) == len(c2):
            # On case-insensitive systems, title and author renames that only
            # change case don't cause any changes to the directories in the file
            # system. This can lead to having the directory names not match the
            # title/author, which leads to trouble when libraries are copied to
            # a case-sensitive system. The following code fixes this by checking
            # each segment. If they are different because of case, then rename
            # the segment to some temp file name, then rename it back to the
            # correct name. Note that the code above correctly handles files in
            # the directories, so no need to do them here.
            for oldseg, newseg in zip(c1, c2):
                if oldseg.lower() == newseg.lower() and oldseg != newseg:
                    while True:
                        # need a temp name in the current segment for renames
                        tempname = os.path.join(curpath, 'TEMP.%f'%time.time())
                        if not os.path.exists(tempname):
                            break
                    os.rename(os.path.join(curpath, oldseg), tempname)
                    os.rename(tempname, os.path.join(curpath, newseg))
                curpath = os.path.join(curpath, newseg)

    def add_listener(self, listener):
        '''
        Add a listener. Will be called on change events with two arguments.
        Event name and list of affected ids.
        '''
        self.listeners.add(listener)

    def notify(self, event, ids=[]):
        'Notify all listeners'
        for listener in self.listeners:
            try:
                listener(event, ids)
            except:
                traceback.print_exc()
                continue

    def cover(self, index, index_is_id=False, as_file=False, as_image=False,
              as_path=False):
        '''
        Return the cover image as a bytestring (in JPEG format) or None.

        `as_file` : If True return the image as an open file object
        `as_image`: If True return the image as a QImage object
        '''
        id = index if  index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if os.access(path, os.R_OK):
            if as_path:
                return path
            try:
                f = open(path, 'rb')
            except (IOError, OSError):
                time.sleep(0.2)
                f = open(path, 'rb')
            if as_image:
                img = QImage()
                img.loadFromData(f.read())
                f.close()
                return img
            ans = f if as_file else f.read()
            if ans is not f:
                f.close()
            return ans

    def get_metadata(self, idx, index_is_id=False, get_cover=False):
        '''
        Convenience method to return metadata as a L{MetaInformation} object.
        '''
        aum = self.authors(idx, index_is_id=index_is_id)
        if aum: aum = [a.strip().replace('|', ',') for a in aum.split(',')]
        mi = MetaInformation(self.title(idx, index_is_id=index_is_id), aum)
        mi.author_sort = self.author_sort(idx, index_is_id=index_is_id)
        if mi.authors:
            mi.author_sort_map = {}
            for name, sort in zip(mi.authors, self.authors_sort_strings(idx,
                index_is_id)):
                mi.author_sort_map[name] = sort
        mi.comments    = self.comments(idx, index_is_id=index_is_id)
        mi.publisher   = self.publisher(idx, index_is_id=index_is_id)
        mi.timestamp   = self.timestamp(idx, index_is_id=index_is_id)
        mi.pubdate     = self.pubdate(idx, index_is_id=index_is_id)
        mi.uuid        = self.uuid(idx, index_is_id=index_is_id)
        mi.title_sort  = self.title_sort(idx, index_is_id=index_is_id)
        tags = self.tags(idx, index_is_id=index_is_id)
        if tags:
            mi.tags = [i.strip() for i in tags.split(',')]
        mi.series = self.series(idx, index_is_id=index_is_id)
        if mi.series:
            mi.series_index = self.series_index(idx, index_is_id=index_is_id)
        mi.rating = self.rating(idx, index_is_id=index_is_id)
        mi.isbn = self.isbn(idx, index_is_id=index_is_id)
        id = idx if index_is_id else self.id(idx)
        mi.application_id = id
        if get_cover:
            mi.cover = self.cover(id, index_is_id=True, as_path=True)
        return mi

    def has_book(self, mi):
        title = mi.title
        if title:
            if not isinstance(title, unicode):
                title = title.decode(preferred_encoding, 'replace')
            return bool(self.conn.get('SELECT id FROM books where title=?', (title,), all=False))
        return False

    def has_cover(self, index, index_is_id=False):
        id = index if  index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        return os.access(path, os.R_OK)

    def remove_cover(self, id, notify=True):
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if os.path.exists(path):
            try:
                os.remove(path)
            except (IOError, OSError):
                time.sleep(0.2)
                os.remove(path)
        if notify:
            self.notify('cover', [id])

    def set_cover(self, id, data, notify=True):
        '''
        Set the cover for this book.

        `data`: Can be either a QImage, QPixmap, file object or bytestring
        '''
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if callable(getattr(data, 'save', None)):
            data.save(path)
        else:
            if callable(getattr(data, 'read', None)):
                data = data.read()
            try:
                save_cover_data_to(data, path)
            except (IOError, OSError):
                time.sleep(0.2)
                save_cover_data_to(data, path)
        if notify:
            self.notify('cover', [id])

    def book_on_device(self, id):
        if callable(self.book_on_device_func):
            return self.book_on_device_func(id)
        return None

    def book_on_device_string(self, id):
        loc = []
        on = self.book_on_device(id)
        if on is not None:
            m, a, b = on
            if m is not None:
                loc.append(_('Main'))
            if a is not None:
                loc.append(_('Card A'))
            if b is not None:
                loc.append(_('Card B'))
        return ', '.join(loc)

    def set_book_on_device_func(self, func):
        self.book_on_device_func = func

    def all_formats(self):
        formats = self.conn.get('SELECT DISTINCT format from data')
        if not formats:
            return set([])
        return set([f[0] for f in formats])

    def formats(self, index, index_is_id=False):
        ''' Return available formats as a comma separated list or None if there are no available formats '''
        id = index if index_is_id else self.id(index)
        try:
            formats = self.conn.get('SELECT format FROM data WHERE book=?', (id,))
            formats = map(lambda x:x[0], formats)
        except:
            return None
        ans = []
        for format in formats:
            if self.format_abspath(id, format, index_is_id=True) is not None:
                ans.append(format)
        if not ans:
            return None
        return ','.join(ans)

    def has_format(self, index, format, index_is_id=False):
        return self.format_abspath(index, format, index_is_id) is not None

    def format_last_modified(self, id_, fmt):
        path = self.format_abspath(id_, fmt, index_is_id=True)
        if path is not None:
            return utcfromtimestamp(os.stat(path).st_mtime)

    def format_abspath(self, index, format, index_is_id=False):
        'Return absolute path to the ebook file of format `format`'
        id = index if index_is_id else self.id(index)
        try:
            name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
        except:
            return None
        if name:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
            format = ('.' + format.lower()) if format else ''
            fmt_path = os.path.join(path, name+format)
            if os.path.exists(fmt_path):
                return fmt_path
            try:
                candidates = glob.glob(os.path.join(path, '*'+format))
            except: # If path contains strange characters this throws an exc
                candidates = []
            if format and candidates and os.path.exists(candidates[0]):
                shutil.copyfile(candidates[0], fmt_path)
                return fmt_path

    def format(self, index, format, index_is_id=False, as_file=False, mode='r+b'):
        '''
        Return the ebook format as a bytestring or `None` if the format doesn't exist,
        or we don't have permission to write to the ebook file.

        `as_file`: If True the ebook format is returned as a file object opened in `mode`
        '''
        path = self.format_abspath(index, format, index_is_id=index_is_id)
        if path is not None:
            f = open(path, mode)
            ret = f if as_file else f.read()
            if not as_file:
                f.close()
            return ret

    def add_format_with_hooks(self, index, format, fpath, index_is_id=False,
                              path=None, notify=True):
        npath = self.run_import_plugins(fpath, format)
        format = os.path.splitext(npath)[-1].lower().replace('.', '').upper()
        stream = open(npath, 'rb')
        format = check_ebook_format(stream, format)
        return self.add_format(index, format, stream,
                               index_is_id=index_is_id, path=path, notify=notify)

    def add_format(self, index, format, stream, index_is_id=False, path=None,
            notify=True, replace=True):
        id = index if index_is_id else self.id(index)
        if path is None:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
        if name:
            if not replace:
                return False
            self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, format))
        name = self.construct_file_name(id)
        ext = ('.' + format.lower()) if format else ''
        dest = os.path.join(path, name+ext)
        pdir = os.path.dirname(dest)
        if not os.path.exists(pdir):
            os.makedirs(pdir)
        with open(dest, 'wb') as f:
            shutil.copyfileobj(stream, f)
        stream.seek(0, 2)
        size=stream.tell()
        self.conn.execute('INSERT INTO data (book,format,uncompressed_size,name) VALUES (?,?,?,?)',
                          (id, format.upper(), size, name))
        self.conn.commit()
        self.refresh_ids([id])
        if notify:
            self.notify('metadata', [id])
        return True

    def delete_book(self, id, notify=True):
        '''
        Removes book from the result cache and the underlying database.
        '''
        try:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        except:
            path = None
        self.data.remove(id)
        if path and os.path.exists(path):
            try:
                winshell.delete_file(path, no_confirm=True, silent=True)
            except:
                self.rmtree(path)
            parent = os.path.dirname(path)
            if len(os.listdir(parent)) == 0:
                self.rmtree(parent)
        self.conn.execute('DELETE FROM books WHERE id=?', (id,))
        self.conn.commit()
        self.clean()
        self.data.books_deleted([id])
        if notify:
            self.notify('delete', [id])

    def remove_format(self, index, format, index_is_id=False, notify=True, commit=True):
        id = index if index_is_id else self.id(index)
        name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
        if name:
            path = self.format_abspath(id, format, index_is_id=True)
            try:
                delete_file(path)
            except:
                traceback.print_exc()
            self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, format.upper()))
            if commit:
                self.conn.commit()
            self.refresh_ids([id])
            if notify:
                self.notify('metadata', [id])

    def clean(self):
        '''
        Remove orphaned entries.
        '''
        def doit(ltable, table, ltable_col):
            st = ('DELETE FROM books_%s_link WHERE (SELECT COUNT(id) '
                    'FROM books WHERE id=book) < 1;')%ltable
            self.conn.execute(st)
            st = ('DELETE FROM %(table)s WHERE (SELECT COUNT(id) '
                    'FROM books_%(ltable)s_link WHERE '
                    '%(ltable_col)s=%(table)s.id) < 1;') % dict(
                            ltable=ltable, table=table, ltable_col=ltable_col)
            self.conn.execute(st)

        for ltable, table, ltable_col in [
                ('authors', 'authors', 'author'),
                ('publishers', 'publishers', 'publisher'),
                ('tags', 'tags', 'tag'),
                ('series', 'series', 'series')
                ]:
            doit(ltable, table, ltable_col)

        for id_, tag in self.conn.get('SELECT id, name FROM tags', all=True):
            if not tag.strip():
                self.conn.execute('DELETE FROM books_tags_link WHERE tag=?',
                        (id_,))
                self.conn.execute('DELETE FROM tags WHERE id=?', (id_,))
        self.clean_custom()
        self.conn.commit()

    def get_recipes(self):
        return self.conn.get('SELECT id, script FROM feeds')

    def get_recipe(self, id):
        return self.conn.get('SELECT script FROM feeds WHERE id=?', (id,), all=False)

    def get_books_for_category(self, category, id_):
        ans = set([])

        if category not in self.field_metadata:
            return ans

        field = self.field_metadata[category]
        ans = self.conn.get(
                'SELECT book FROM books_{tn}_link WHERE {col}=?'.format(
                    tn=field['table'], col=field['link_column']), (id_,))
        return set(x[0] for x in ans)

    CATEGORY_SORTS = ('name', 'popularity', 'rating')

    def get_categories(self, sort='name', ids=None, icon_map=None):
        self.books_list_filter.change([] if not ids else ids)

        categories = {}
        if icon_map is not None and type(icon_map) != TagsIcons:
            raise TypeError('icon_map passed to get_categories must be of type TagIcons')

        tb_cats = self.field_metadata
        #### First, build the standard and custom-column categories ####
        for category in tb_cats.keys():
            cat = tb_cats[category]
            if not cat['is_category'] or cat['kind'] in ['user', 'search']:
                continue
            tn = cat['table']
            categories[category] = []   #reserve the position in the ordered list
            if tn is None:              # Nothing to do for the moment
                continue
            cn = cat['column']
            if ids is None:
                query = '''SELECT id, {0}, count, avg_rating, sort
                           FROM tag_browser_{1}'''.format(cn, tn)
            else:
                query = '''SELECT id, {0}, count, avg_rating, sort
                           FROM tag_browser_filtered_{1}'''.format(cn, tn)
            if sort == 'popularity':
                query += ' ORDER BY count DESC, sort ASC'
            elif sort == 'name':
                query += ' ORDER BY sort ASC'
            else:
                query += ' ORDER BY avg_rating DESC, sort ASC'
            data = self.conn.get(query)

            # icon_map is not None if get_categories is to store an icon and
            # possibly a tooltip in the tag structure.
            icon, tooltip = None, ''
            label = tb_cats.key_to_label(category)
            if icon_map:
                if not tb_cats.is_custom_field(category):
                    if category in icon_map:
                        icon = icon_map[label]
                else:
                    icon = icon_map[':custom']
                    icon_map[category] = icon
                    tooltip = self.custom_column_label_map[label]['name']

            datatype = cat['datatype']
            if datatype == 'rating':
                # eliminate the zero ratings line as well as count == 0
                item_not_zero_func = (lambda x: x[1] > 0 and x[2] > 0)
                formatter = (lambda x:u'\u2605'*int(x/2))
            elif category == 'authors':
                item_not_zero_func = (lambda x: x[2] > 0)
                # Clean up the authors strings to human-readable form
                formatter = (lambda x: x.replace('|', ','))
            else:
                item_not_zero_func = (lambda x: x[2] > 0)
                formatter = (lambda x:unicode(x))

            categories[category] = [Tag(formatter(r[1]), count=r[2], id=r[0],
                                        avg=r[3], sort=r[4],
                                        icon=icon, tooltip=tooltip)
                                    for r in data if item_not_zero_func(r)]

        # Needed for legacy databases that have multiple ratings that
        # map to n stars
        for r in categories['rating']:
            for x in categories['rating']:
                if r.name == x.name and r.id != x.id:
                    r.count = r.count + x.count
                    categories['rating'].remove(x)
                    break

        # We delayed computing the standard formats category because it does not
        # use a view, but is computed dynamically
        categories['formats'] = []
        icon = None
        if icon_map and 'formats' in icon_map:
                icon = icon_map['formats']
        for fmt in self.conn.get('SELECT DISTINCT format FROM data'):
            fmt = fmt[0]
            if ids is not None:
                count = self.conn.get('''SELECT COUNT(id)
                                       FROM data
                                       WHERE format="%s" AND
                                       books_list_filter(book)'''%fmt,
                                       all=False)
            else:
                count = self.conn.get('''SELECT COUNT(id)
                                       FROM data
                                       WHERE format="%s"'''%fmt,
                                       all=False)
            if count > 0:
                categories['formats'].append(Tag(fmt, count=count, icon=icon))

        if sort == 'popularity':
            categories['formats'].sort(key=lambda x: x.count, reverse=True)
        else: # no ratings exist to sort on
            categories['formats'].sort(key = lambda x:x.name)

        #### Now do the user-defined categories. ####
        user_categories = self.prefs['user_categories']

        # We want to use same node in the user category as in the source
        # category. To do that, we need to find the original Tag node. There is
        # a time/space tradeoff here. By converting the tags into a map, we can
        # do the verification in the category loop much faster, at the cost of
        # temporarily duplicating the categories lists.
        taglist = {}
        for c in categories.keys():
            taglist[c] = dict(map(lambda t:(t.name, t), categories[c]))

        for user_cat in sorted(user_categories.keys()):
            items = []
            for (name,label,ign) in user_categories[user_cat]:
                if label in taglist and name in taglist[label]:
                    items.append(taglist[label][name])
                # else: do nothing, to not include nodes w zero counts
            if len(items):
                cat_name = user_cat+':' # add the ':' to avoid name collision
                # Not a problem if we accumulate entries in the icon map
                if icon_map is not None:
                    icon_map[cat_name] = icon_map[':user']
                if sort == 'popularity':
                    categories[cat_name] = \
                        sorted(items, key=lambda x: x.count, reverse=True)
                elif sort == 'name':
                    categories[cat_name] = \
                        sorted(items, key=lambda x: x.sort.lower())
                else:
                    categories[cat_name] = \
                        sorted(items, key=lambda x:x.avg_rating, reverse=True)

        #### Finally, the saved searches category ####
        items = []
        icon = None
        if icon_map and 'search' in icon_map:
                icon = icon_map['search']
        for srch in saved_searches().names():
            items.append(Tag(srch, tooltip=saved_searches().lookup(srch), icon=icon))
        if len(items):
            if icon_map is not None:
                icon_map['search'] = icon_map['search']
            categories['search'] = items

        return categories

    def tags_older_than(self, tag, delta):
        tag = tag.lower().strip()
        now = nowf()
        for r in self.data._data:
            if r is not None:
                if (now - r[self.FIELD_MAP['timestamp']]) > delta:
                    tags = r[self.FIELD_MAP['tags']]
                    if tags and tag in tags.lower():
                        yield r[self.FIELD_MAP['id']]

    def get_next_series_num_for(self, series):
        series_id = self.conn.get('SELECT id from series WHERE name=?',
                (series,), all=False)
        if series_id is None:
            return 1.0
        series_num = self.conn.get(
            ('SELECT MAX(series_index) FROM books WHERE id IN '
            '(SELECT book FROM books_series_link where series=?)'),
            (series_id,), all=False)
        if series_num is None:
            return 1.0
        return floor(series_num+1)

    def set(self, row, column, val):
        '''
        Convenience method for setting the title, authors, publisher or rating
        '''
        id = self.data[row][0]
        col = {'title':1, 'authors':2, 'publisher':3, 'rating':4, 'tags':7}[column]

        self.data.set(row, col, val)
        if column == 'authors':
            val = string_to_authors(val)
            self.set_authors(id, val, notify=False)
        elif column == 'title':
            self.set_title(id, val, notify=False)
        elif column == 'publisher':
            self.set_publisher(id, val, notify=False)
        elif column == 'rating':
            self.set_rating(id, val, notify=False)
        elif column == 'tags':
            self.set_tags(id, [x.strip() for x in val.split(',') if x.strip()],
                    append=False, notify=False)
        self.data.refresh_ids(self, [id])
        self.set_path(id, True)
        self.notify('metadata', [id])

    def set_metadata(self, id, mi, ignore_errors=False):
        '''
        Set metadata for the book `id` from the `MetaInformation` object `mi`
        '''
        def doit(func, *args, **kwargs):
            try:
                func(*args, **kwargs)
            except:
                if ignore_errors:
                    traceback.print_exc()
                else:
                    raise
        if mi.title:
            self.set_title(id, mi.title)
        if not mi.authors:
                mi.authors = [_('Unknown')]
        authors = []
        for a in mi.authors:
            authors += string_to_authors(a)
        self.set_authors(id, authors, notify=False)
        if mi.author_sort:
            doit(self.set_author_sort, id, mi.author_sort, notify=False)
        if mi.publisher:
            doit(self.set_publisher, id, mi.publisher, notify=False)
        if mi.rating:
            doit(self.set_rating, id, mi.rating, notify=False)
        if mi.series:
            doit(self.set_series, id, mi.series, notify=False)
        if mi.cover_data[1] is not None:
            doit(self.set_cover, id, mi.cover_data[1]) # doesn't use commit
        elif mi.cover is not None and os.access(mi.cover, os.R_OK):
            doit(self.set_cover, id, open(mi.cover, 'rb'))
        if mi.tags:
            doit(self.set_tags, id, mi.tags, notify=False)
        if mi.comments:
            doit(self.set_comment, id, mi.comments, notify=False)
        if mi.isbn and mi.isbn.strip():
            doit(self.set_isbn, id, mi.isbn, notify=False)
        if mi.series_index:
            doit(self.set_series_index, id, mi.series_index, notify=False)
        if mi.pubdate:
            doit(self.set_pubdate, id, mi.pubdate, notify=False)
        if getattr(mi, 'timestamp', None) is not None:
            doit(self.set_timestamp, id, mi.timestamp, notify=False)
        self.set_path(id, True)
        self.notify('metadata', [id])

    # Given a book, return the list of author sort strings for the book's authors
    def authors_sort_strings(self, id, index_is_id=False):
        id = id if index_is_id else self.id(id)
        aut_strings = self.conn.get('''
                        SELECT sort
                        FROM authors, books_authors_link as bl
                        WHERE bl.book=? and authors.id=bl.author
                        ORDER BY bl.id''', (id,))
        result = []
        for (sort,) in aut_strings:
            result.append(sort)
        return result

    # Given a book, return the author_sort string for authors of the book
    def author_sort_from_book(self, id, index_is_id=False):
        auts = self.authors_sort_strings(id, index_is_id)
        return ' & '.join(auts).replace('|', ',')

    # Given a list of authors, return the author_sort string for the authors,
    # preferring the author sort associated with the author over the computed
    # string
    def author_sort_from_authors(self, authors):
        result = []
        for aut in authors:
            r = self.conn.get('SELECT sort FROM authors WHERE name=?',
                              (aut.replace(',', '|'),), all=False)
            if r is None:
                result.append(author_to_author_sort(aut))
            else:
                result.append(r)
        return ' & '.join(result).replace('|', ',')

    def set_authors(self, id, authors, notify=True):
        '''
        `authors`: A list of authors.
        '''
        if not authors:
            authors = [_('Unknown')]
        self.conn.execute('DELETE FROM books_authors_link WHERE book=?',(id,))
        self.conn.execute('DELETE FROM authors WHERE (SELECT COUNT(id) FROM books_authors_link WHERE author=authors.id) < 1')
        for a in authors:
            if not a:
                continue
            a = a.strip().replace(',', '|')
            if not isinstance(a, unicode):
                a = a.decode(preferred_encoding, 'replace')
            author = self.conn.get('SELECT id from authors WHERE name=?', (a,), all=False)
            if author:
                aid = author
                # Handle change of case
                self.conn.execute('UPDATE authors SET name=? WHERE id=?', (a, aid))
            else:
                aid = self.conn.execute('INSERT INTO authors(name) VALUES (?)', (a,)).lastrowid
            try:
                self.conn.execute('INSERT INTO books_authors_link(book, author) VALUES (?,?)',
                                   (id, aid))
            except IntegrityError: # Sometimes books specify the same author twice in their metadata
                pass
        ss = self.author_sort_from_book(id, index_is_id=True)
        self.conn.execute('UPDATE books SET author_sort=? WHERE id=?',
                          (ss, id))
        self.conn.commit()
        self.data.set(id, self.FIELD_MAP['authors'],
                      ','.join([a.replace(',', '|') for a in authors]),
                      row_is_id=True)
        self.data.set(id, self.FIELD_MAP['author_sort'], ss, row_is_id=True)
        self.set_path(id, True)
        if notify:
            self.notify('metadata', [id])

    def set_title(self, id, title, notify=True):
        if not title:
            return
        if not isinstance(title, unicode):
            title = title.decode(preferred_encoding, 'replace')
        self.conn.execute('UPDATE books SET title=? WHERE id=?', (title, id))
        self.data.set(id, self.FIELD_MAP['title'], title, row_is_id=True)
        if tweaks['title_series_sorting'] == 'library_order':
            self.data.set(id, self.FIELD_MAP['sort'], title_sort(title), row_is_id=True)
        else:
            self.data.set(id, self.FIELD_MAP['sort'], title, row_is_id=True)
        self.set_path(id, True)
        self.conn.commit()
        if notify:
            self.notify('metadata', [id])

    def set_timestamp(self, id, dt, notify=True, commit=True):
        if dt:
            self.conn.execute('UPDATE books SET timestamp=? WHERE id=?', (dt, id))
            self.data.set(id, self.FIELD_MAP['timestamp'], dt, row_is_id=True)
            if commit:
                self.conn.commit()
            if notify:
                self.notify('metadata', [id])

    def set_pubdate(self, id, dt, notify=True, commit=True):
        if dt:
            self.conn.execute('UPDATE books SET pubdate=? WHERE id=?', (dt, id))
            self.data.set(id, self.FIELD_MAP['pubdate'], dt, row_is_id=True)
            if commit:
                self.conn.commit()
            if notify:
                self.notify('metadata', [id])


    def set_publisher(self, id, publisher, notify=True, commit=True):
        self.conn.execute('DELETE FROM books_publishers_link WHERE book=?',(id,))
        self.conn.execute('DELETE FROM publishers WHERE (SELECT COUNT(id) FROM books_publishers_link WHERE publisher=publishers.id) < 1')
        if publisher:
            if not isinstance(publisher, unicode):
                publisher = publisher.decode(preferred_encoding, 'replace')
            pub = self.conn.get('SELECT id from publishers WHERE name=?', (publisher,), all=False)
            if pub:
                aid = pub
            else:
                aid = self.conn.execute('INSERT INTO publishers(name) VALUES (?)', (publisher,)).lastrowid
            self.conn.execute('INSERT INTO books_publishers_link(book, publisher) VALUES (?,?)', (id, aid))
            if commit:
                self.conn.commit()
            self.data.set(id, self.FIELD_MAP['publisher'], publisher, row_is_id=True)
            if notify:
                self.notify('metadata', [id])

    # Convenience methods for tags_list_editor
    # Note: we generally do not need to refresh_ids because library_view will
    # refresh everything.
    def get_tags_with_ids(self):
        result = self.conn.get('SELECT id,name FROM tags')
        if not result:
            return []
        return result

    def rename_tag(self, old_id, new_name):
        new_name = new_name.strip()
        new_id = self.conn.get(
                    '''SELECT id from tags
                       WHERE name=?''', (new_name,), all=False)
        if new_id is None or old_id == new_id:
            # easy cases. Simply rename the tag. Do it even if equal, in case
            # there is a change of case
            self.conn.execute('''UPDATE tags SET name=?
                                 WHERE id=?''', (new_name, old_id))
        else:
            # It is possible that by renaming a tag, the tag will appear
            # twice on a book. This will throw an integrity error, aborting
            # all the changes. To get around this, we first delete any links
            # to the new_id from books referencing the old_id, so that
            # renaming old_id to new_id will be unique on the book
            books = self.conn.get('''SELECT book from books_tags_link
                                     WHERE tag=?''', (old_id,))
            for (book_id,) in books:
                self.conn.execute('''DELETE FROM books_tags_link
                                     WHERE book=? and tag=?''', (book_id, new_id))

            # Change the link table to point at the new tag
            self.conn.execute('''UPDATE books_tags_link SET tag=?
                                 WHERE tag=?''',(new_id, old_id,))
            # Get rid of the no-longer used publisher
            self.conn.execute('DELETE FROM tags WHERE id=?', (old_id,))
        self.conn.commit()

    def delete_tag_using_id(self, id):
        self.conn.execute('DELETE FROM books_tags_link WHERE tag=?', (id,))
        self.conn.execute('DELETE FROM tags WHERE id=?', (id,))
        self.conn.commit()

    def get_series_with_ids(self):
        result = self.conn.get('SELECT id,name FROM series')
        if not result:
            return []
        return result

    def rename_series(self, old_id, new_name):
        new_name = new_name.strip()
        new_id = self.conn.get(
                    '''SELECT id from series
                       WHERE name=?''', (new_name,), all=False)
        if new_id is None or old_id == new_id:
            self.conn.execute('UPDATE series SET name=? WHERE id=?',
                              (new_name, old_id))
        else:
            # New series exists. Must update the link, then assign a
            # new series index to each of the books.

            # Get the list of books where we must update the series index
            books = self.conn.get('''SELECT books.id
                                     FROM books, books_series_link as lt
                                     WHERE books.id = lt.book AND lt.series=?
                                     ORDER BY books.series_index''', (old_id,))
            # Get the next series index
            index = self.get_next_series_num_for(new_name)
            # Now update the link table
            self.conn.execute('''UPDATE books_series_link
                                 SET series=?
                                 WHERE series=?''',(new_id, old_id,))
            # Now set the indices
            for (book_id,) in books:
                self.conn.execute('''UPDATE books
                                     SET series_index=?
                                     WHERE id=?''',(index, book_id,))
                index = index + 1
        self.conn.commit()

    def delete_series_using_id(self, id):
        books = self.conn.get('SELECT book from books_series_link WHERE series=?', (id,))
        self.conn.execute('DELETE FROM books_series_link WHERE series=?', (id,))
        self.conn.execute('DELETE FROM series WHERE id=?', (id,))
        self.conn.commit()
        for (book_id,) in books:
            self.conn.execute('UPDATE books SET series_index=1.0 WHERE id=?', (book_id,))

    def get_publishers_with_ids(self):
        result = self.conn.get('SELECT id,name FROM publishers')
        if not result:
            return []
        return result

    def rename_publisher(self, old_id, new_name):
        new_name = new_name.strip()
        new_id = self.conn.get(
                    '''SELECT id from publishers
                       WHERE name=?''', (new_name,), all=False)
        if new_id is None or old_id == new_id:
            # New name doesn't exist. Simply change the old name
            self.conn.execute('UPDATE publishers SET name=? WHERE id=?', \
                              (new_name, old_id))
        else:
            # Change the link table to point at the new one
            self.conn.execute('''UPDATE books_publishers_link
                                 SET publisher=?
                                 WHERE publisher=?''',(new_id, old_id,))
            # Get rid of the no-longer used publisher
            self.conn.execute('DELETE FROM publishers WHERE id=?', (old_id,))
        self.conn.commit()

    def delete_publisher_using_id(self, old_id):
        self.conn.execute('''DELETE FROM books_publishers_link
                             WHERE publisher=?''', (old_id,))
        self.conn.execute('DELETE FROM publishers WHERE id=?', (old_id,))
        self.conn.commit()

    def get_authors_with_ids(self):
        result = self.conn.get('SELECT id,name,sort FROM authors')
        if not result:
            return []
        return result

    def set_sort_field_for_author(self, old_id, new_sort):
        self.conn.execute('UPDATE authors SET sort=? WHERE id=?', \
                              (new_sort.strip(), old_id))
        self.conn.commit()
        # Now change all the author_sort fields in books by this author
        bks = self.conn.get('SELECT book from books_authors_link WHERE author=?', (old_id,))
        for (book_id,) in bks:
            ss = self.author_sort_from_book(book_id, index_is_id=True)
            self.set_author_sort(book_id, ss)

    def rename_author(self, old_id, new_name):
        # Make sure that any commas in new_name are changed to '|'!
        new_name = new_name.replace(',', '|').strip()

        # Get the list of books we must fix up, one way or the other
        # Save the list so we can use it twice
        bks = self.conn.get('SELECT book from books_authors_link WHERE author=?', (old_id,))
        books = []
        for (book_id,) in bks:
            books.append(book_id)

        # check if the new author already exists
        new_id = self.conn.get('SELECT id from authors WHERE name=?',
                                (new_name,), all=False)
        if new_id is None or old_id == new_id:
            # No name clash. Go ahead and update the author's name
            self.conn.execute('UPDATE authors SET name=? WHERE id=?',
                              (new_name, old_id))
        else:
            # First check for the degenerate case -- changing a value to itself.
            # Update it in case there is a change of case, but do nothing else
            if old_id == new_id:
                self.conn.execute('UPDATE authors SET name=? WHERE id=?',
                              (new_name, old_id))
                self.conn.commit()
                return new_id
            # Author exists. To fix this, we must replace all the authors
            # instead of replacing the one. Reason: db integrity checks can stop
            # the rename process, which would leave everything half-done. We
            # can't do it the same way as tags (delete and add) because author
            # order is important.

            for book_id in books:
                # Get the existing list of authors
                authors = self.conn.get('''
                    SELECT author from books_authors_link
                    WHERE book=?
                    ORDER BY id''',(book_id,))

                # unpack the double-list structure, replacing the old author
                # with the new one while we are at it
                for i,aut in enumerate(authors):
                    authors[i] = aut[0] if aut[0] != old_id else new_id
                # Delete the existing authors list
                self.conn.execute('''DELETE FROM books_authors_link
                                     WHERE book=?''',(book_id,))
                # Change the authors to the new list
                for aid in authors:
                    try:
                        self.conn.execute('''
                            INSERT INTO books_authors_link(book, author)
                            VALUES (?,?)''', (book_id, aid))
                    except IntegrityError:
                        # Sometimes books specify the same author twice in their
                        # metadata. Ignore it.
                        pass
            # Now delete the old author from the DB
            bks = self.conn.get('SELECT book FROM books_authors_link WHERE author=?', (old_id,))
            self.conn.execute('DELETE FROM authors WHERE id=?', (old_id,))
        self.conn.commit()
        # the authors are now changed, either by changing the author's name
        # or replacing the author in the list. Now must fix up the books.
        for book_id in books:
            # First, must refresh the cache to see the new authors
            self.data.refresh_ids(self, [book_id])
            # now fix the filesystem paths
            self.set_path(book_id, index_is_id=True)
            # Next fix the author sort. Reset it to the default
            ss = self.author_sort_from_book(book_id, index_is_id=True)
            self.set_author_sort(book_id, ss)
            # the caller will do a general refresh, so we don't need to
            # do one here
        return new_id

    # end convenience methods

    def get_tags(self, id):
        result = self.conn.get(
        'SELECT name FROM tags WHERE id IN (SELECT tag FROM books_tags_link WHERE book=?)',
        (id,), all=True)
        if not result:
            return set([])
        return set([r[0] for r in result])

    @classmethod
    def cleanup_tags(cls, tags):
        tags = [x.strip() for x in tags if x.strip()]
        tags = [x.decode(preferred_encoding, 'replace') \
                    if isbytestring(x) else x for x in tags]
        tags = [u' '.join(x.split()) for x in tags]
        ans, seen = [], set([])
        for tag in tags:
            if tag.lower() not in seen:
                seen.add(tag.lower())
                ans.append(tag)
        return ans

    def bulk_modify_tags(self, ids, add=[], remove=[], notify=False):
        add = self.cleanup_tags(add)
        remove = self.cleanup_tags(remove)
        remove = set(remove) - set(add)
        if not ids or (not add and not remove):
            return

        # Add tags that do not already exist into the tag table
        all_tags = self.all_tags()
        lt = [t.lower() for t in all_tags]
        new_tags = [t for t in add if t.lower() not in lt]
        if new_tags:
            self.conn.executemany('INSERT INTO tags(name) VALUES (?)', [(x,) for x in
                new_tags])

        # Create the temporary tables to store the ids for books and tags
        # to be operated on
        tables = ('temp_bulk_tag_edit_books', 'temp_bulk_tag_edit_add',
                    'temp_bulk_tag_edit_remove')
        drops = '\n'.join(['DROP TABLE IF EXISTS %s;'%t for t in tables])
        creates = '\n'.join(['CREATE TEMP TABLE %s(id INTEGER PRIMARY KEY);'%t
                for t in tables])
        self.conn.executescript(drops + creates)

        # Populate the books temp table
        self.conn.executemany(
            'INSERT INTO temp_bulk_tag_edit_books VALUES (?)',
                [(x,) for x in ids])

        # Populate the add/remove tags temp tables
        for table, tags in enumerate([add, remove]):
            if not tags:
                continue
            table = tables[table+1]
            insert = ('INSERT INTO %s(id) SELECT tags.id FROM tags WHERE name=?'
                     ' COLLATE PYNOCASE LIMIT 1')
            self.conn.executemany(insert%table, [(x,) for x in tags])

        if remove:
            self.conn.execute(
              '''DELETE FROM books_tags_link WHERE
                    book IN (SELECT id FROM %s) AND
                    tag IN (SELECT id FROM %s)'''
              % (tables[0], tables[2]))

        if add:
            self.conn.execute(
            '''
            INSERT OR REPLACE INTO books_tags_link(book, tag) SELECT {0}.id, {1}.id FROM
            {0}, {1}
            '''.format(tables[0], tables[1])
            )
        self.conn.executescript(drops)
        self.conn.commit()

        for x in ids:
            tags = u','.join(self.get_tags(x))
            self.data.set(x, self.FIELD_MAP['tags'], tags, row_is_id=True)
        if notify:
            self.notify('metadata', ids)

    def commit(self):
        self.conn.commit()

    def set_tags(self, id, tags, append=False, notify=True, commit=True):
        '''
        @param tags: list of strings
        @param append: If True existing tags are not removed
        '''
        if not append:
            self.conn.execute('DELETE FROM books_tags_link WHERE book=?', (id,))
            self.conn.execute('DELETE FROM tags WHERE (SELECT COUNT(id) FROM books_tags_link WHERE tag=tags.id) < 1')
        otags = self.get_tags(id)
        tags = self.cleanup_tags(tags)
        for tag in (set(tags)-otags):
            tag = tag.strip()
            if not tag:
                continue
            if not isinstance(tag, unicode):
                tag = tag.decode(preferred_encoding, 'replace')
            existing_tags = self.all_tags()
            lt = [t.lower() for t in existing_tags]
            try:
                idx = lt.index(tag.lower())
            except ValueError:
                idx = -1
            if idx > -1:
                etag = existing_tags[idx]
                tid = self.conn.get('SELECT id FROM tags WHERE name=?', (etag,), all=False)
                if etag != tag:
                    self.conn.execute('UPDATE tags SET name=? WHERE id=?', (tag, tid))
            else:
                tid = self.conn.execute('INSERT INTO tags(name) VALUES(?)', (tag,)).lastrowid

            if not self.conn.get('SELECT book FROM books_tags_link WHERE book=? AND tag=?',
                                        (id, tid), all=False):
                self.conn.execute('INSERT INTO books_tags_link(book, tag) VALUES (?,?)',
                              (id, tid))
        if commit:
            self.conn.commit()
        tags = u','.join(self.get_tags(id))
        self.data.set(id, self.FIELD_MAP['tags'], tags, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def unapply_tags(self, book_id, tags, notify=True):
        for tag in tags:
            id = self.conn.get('SELECT id FROM tags WHERE name=?', (tag,), all=False)
            if id:
                self.conn.execute('DELETE FROM books_tags_link WHERE tag=? AND book=?', (id, book_id))
        self.conn.commit()
        self.data.refresh_ids(self, [book_id])
        if notify:
            self.notify('metadata', [id])

    def is_tag_used(self, tag):
        existing_tags = self.all_tags()
        lt = [t.lower() for t in existing_tags]
        try:
            lt.index(tag.lower())
            return True
        except ValueError:
            return False

    def delete_tag(self, tag):
        existing_tags = self.all_tags()
        lt = [t.lower() for t in existing_tags]
        try:
            idx = lt.index(tag.lower())
        except ValueError:
            idx = -1
        if idx > -1:
            id = self.conn.get('SELECT id FROM tags WHERE name=?', (existing_tags[idx],), all=False)
            if id:
                self.conn.execute('DELETE FROM books_tags_link WHERE tag=?', (id,))
                self.conn.execute('DELETE FROM tags WHERE id=?', (id,))
                self.conn.commit()

    def set_series(self, id, series, notify=True, commit=True):
        self.conn.execute('DELETE FROM books_series_link WHERE book=?',(id,))
        self.conn.execute('DELETE FROM series WHERE (SELECT COUNT(id) FROM books_series_link WHERE series=series.id) < 1')
        if series:
            if not isinstance(series, unicode):
                series = series.decode(preferred_encoding, 'replace')
            series = series.strip()
            series = u' '.join(series.split())
            s = self.conn.get('SELECT id from series WHERE name=?', (series,), all=False)
            if s:
                aid = s
            else:
                aid = self.conn.execute('INSERT INTO series(name) VALUES (?)', (series,)).lastrowid
            self.conn.execute('INSERT INTO books_series_link(book, series) VALUES (?,?)', (id, aid))
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['series'], series, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_series_index(self, id, idx, notify=True, commit=True):
        if idx is None:
            idx = 1.0
        try:
            idx = float(idx)
        except:
            idx = 1.0
        self.conn.execute('UPDATE books SET series_index=? WHERE id=?', (idx, id))
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['series_index'], idx, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_rating(self, id, rating, notify=True, commit=True):
        rating = int(rating)
        self.conn.execute('DELETE FROM books_ratings_link WHERE book=?',(id,))
        rat = self.conn.get('SELECT id FROM ratings WHERE rating=?', (rating,), all=False)
        rat = rat if rat else self.conn.execute('INSERT INTO ratings(rating) VALUES (?)', (rating,)).lastrowid
        self.conn.execute('INSERT INTO books_ratings_link(book, rating) VALUES (?,?)', (id, rat))
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['rating'], rating, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_comment(self, id, text, notify=True, commit=True):
        self.conn.execute('DELETE FROM comments WHERE book=?', (id,))
        self.conn.execute('INSERT INTO comments(book,text) VALUES (?,?)', (id, text))
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['comments'], text, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_author_sort(self, id, sort, notify=True, commit=True):
        self.conn.execute('UPDATE books SET author_sort=? WHERE id=?', (sort, id))
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['author_sort'], sort, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_isbn(self, id, isbn, notify=True, commit=True):
        self.conn.execute('UPDATE books SET isbn=? WHERE id=?', (isbn, id))
        if commit:
            self.conn.commit()
        self.data.set(id, self.FIELD_MAP['isbn'], isbn, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def add_catalog(self, path, title):
        format = os.path.splitext(path)[1][1:].lower()
        with open(path, 'rb') as stream:
            matches = self.data.get_matches('title', '='+title)
            if matches:
                tag_matches = self.data.get_matches('tags', '='+_('Catalog'))
                matches = matches.intersection(tag_matches)
            db_id = None
            if matches:
                db_id = list(matches)[0]
            if db_id is None:
                obj = self.conn.execute('INSERT INTO books(title, author_sort) VALUES (?, ?)',
                                    (title, 'calibre'))
                db_id = obj.lastrowid
                self.data.books_added([db_id], self)
                self.set_path(db_id, index_is_id=True)
                self.conn.commit()
            try:
                mi = get_metadata(stream, format)
            except:
                mi = MetaInformation(title, ['calibre'])
            stream.seek(0)
            mi.title, mi.authors = title, ['calibre']
            mi.tags = [_('Catalog')]
            mi.pubdate = mi.timestamp = utcnow()
            if format == 'mobi':
                mi.cover, mi.cover_data = None, (None, None)
            self.set_metadata(db_id, mi)
            self.add_format(db_id, format, stream, index_is_id=True)

        self.conn.commit()
        self.data.refresh_ids(self, [db_id]) # Needed to update format list and size
        return db_id


    def add_news(self, path, arg):
        format = os.path.splitext(path)[1][1:].lower()
        stream = path if hasattr(path, 'read') else open(path, 'rb')
        stream.seek(0)
        mi = get_metadata(stream, format, use_libprs_metadata=False)
        stream.seek(0)
        mi.series_index = 1.0
        mi.tags = [_('News')]
        if arg['add_title_tag']:
            mi.tags += [arg['title']]
        if arg['custom_tags']:
            mi.tags += arg['custom_tags']
        obj = self.conn.execute('INSERT INTO books(title, author_sort) VALUES (?, ?)',
                              (mi.title, mi.authors[0]))
        id = obj.lastrowid
        self.data.books_added([id], self)
        self.set_path(id, index_is_id=True)
        self.conn.commit()
        if mi.pubdate is None:
            mi.pubdate = utcnow()
        if mi.timestamp is None:
            mi.timestamp = utcnow()
        self.set_metadata(id, mi)

        self.add_format(id, format, stream, index_is_id=True)
        if not hasattr(path, 'read'):
            stream.close()
        self.conn.commit()
        self.data.refresh_ids(self, [id]) # Needed to update format list and size
        return id

    def run_import_plugins(self, path_or_stream, format):
        format = format.lower()
        if hasattr(path_or_stream, 'seek'):
            path_or_stream.seek(0)
            pt = PersistentTemporaryFile('_import_plugin.'+format)
            shutil.copyfileobj(path_or_stream, pt, 1024**2)
            pt.close()
            path = pt.name
        else:
            path = path_or_stream
        return run_plugins_on_import(path, format)

    def create_book_entry(self, mi, cover=None, add_duplicates=True):
        if not add_duplicates and self.has_book(mi):
            return None
        series_index = 1.0 if mi.series_index is None else mi.series_index
        aus = mi.author_sort if mi.author_sort else self.author_sort_from_authors(mi.authors)
        title = mi.title
        if isinstance(aus, str):
            aus = aus.decode(preferred_encoding, 'replace')
        if isinstance(title, str):
            title = title.decode(preferred_encoding)
        obj = self.conn.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                            (title, series_index, aus))
        id = obj.lastrowid
        self.data.books_added([id], self)
        self.set_path(id, True)
        self.conn.commit()
        if mi.timestamp is None:
            mi.timestamp = utcnow()
        if mi.pubdate is None:
            mi.pubdate = utcnow()
        self.set_metadata(id, mi)
        if cover is not None:
            try:
                self.set_cover(id, cover)
            except:
                traceback.print_exc()
        return id


    def add_books(self, paths, formats, metadata, add_duplicates=True):
        '''
        Add a book to the database. The result cache is not updated.
        :param:`paths` List of paths to book files or file-like objects
        '''
        formats, metadata = iter(formats), iter(metadata)
        duplicates = []
        ids = []
        for path in paths:
            mi = metadata.next()
            format = formats.next()
            if not add_duplicates and self.has_book(mi):
                duplicates.append((path, format, mi))
                continue
            series_index = 1.0 if mi.series_index is None else mi.series_index
            aus = mi.author_sort if mi.author_sort else self.author_sort_from_authors(mi.authors)
            title = mi.title
            if isinstance(aus, str):
                aus = aus.decode(preferred_encoding, 'replace')
            if isinstance(title, str):
                title = title.decode(preferred_encoding)
            obj = self.conn.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                              (title, series_index, aus))
            id = obj.lastrowid
            self.data.books_added([id], self)
            ids.append(id)
            self.set_path(id, True)
            self.conn.commit()
            if mi.timestamp is None:
                mi.timestamp = utcnow()
            if mi.pubdate is None:
                mi.pubdate = utcnow()
            self.set_metadata(id, mi)
            npath = self.run_import_plugins(path, format)
            format = os.path.splitext(npath)[-1].lower().replace('.', '').upper()
            stream = open(npath, 'rb')
            format = check_ebook_format(stream, format)
            self.add_format(id, format, stream, index_is_id=True)
            stream.close()
        self.conn.commit()
        self.data.refresh_ids(self, ids) # Needed to update format list and size
        if duplicates:
            paths    = list(duplicate[0] for duplicate in duplicates)
            formats  = list(duplicate[1] for duplicate in duplicates)
            metadata = list(duplicate[2] for duplicate in duplicates)
            return (paths, formats, metadata), len(ids)
        return None, len(ids)

    def import_book(self, mi, formats, notify=True):
        series_index = 1.0 if mi.series_index is None else mi.series_index
        if not mi.title:
            mi.title = _('Unknown')
        if not mi.authors:
            mi.authors = [_('Unknown')]
        aus = mi.author_sort if mi.author_sort else self.author_sort_from_authors(mi.authors)
        if isinstance(aus, str):
            aus = aus.decode(preferred_encoding, 'replace')
        title = mi.title if isinstance(mi.title, unicode) else \
                mi.title.decode(preferred_encoding, 'replace')
        obj = self.conn.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                          (title, series_index, aus))
        id = obj.lastrowid
        self.data.books_added([id], self)
        self.set_path(id, True)
        if mi.timestamp is None:
            mi.timestamp = utcnow()
        if mi.pubdate is None:
            mi.pubdate = utcnow()
        self.set_metadata(id, mi, ignore_errors=True)
        for path in formats:
            ext = os.path.splitext(path)[1][1:].lower()
            if ext == 'opf':
                continue
            self.add_format_with_hooks(id, ext, path, index_is_id=True)
        self.conn.commit()
        self.data.refresh_ids(self, [id]) # Needed to update format list and size
        if notify:
            self.notify('add', [id])
        return id

    def get_top_level_move_items(self):
        items = set(os.listdir(self.library_path))
        paths = set([])
        for x in self.data.universal_set():
            path = self.path(x, index_is_id=True)
            path = path.split(os.sep)[0]
            paths.add(path)
        paths.add('metadata.db')
        path_map = {}
        for x in paths:
            path_map[x] = x
        if not self.is_case_sensitive:
            for x in items:
                path_map[x.lower()] = x
            items = set(path_map)
            paths = set([x.lower() for x in paths])
        items = items.intersection(paths)
        return items, path_map

    def move_library_to(self, newloc, progress=lambda x: x):
        if not os.path.exists(newloc):
            os.makedirs(newloc)
        old_dirs = set([])
        items, path_map = self.get_top_level_move_items()
        for x in items:
            src = os.path.join(self.library_path, x)
            dest = os.path.join(newloc, path_map[x])
            if os.path.isdir(src):
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
                old_dirs.add(src)
            else:
                if os.path.exists(dest):
                    os.remove(dest)
                shutil.copyfile(src, dest)
            x = path_map[x]
            if not isinstance(x, unicode):
                x = x.decode(filesystem_encoding, 'replace')
            progress(x)

        dbpath = os.path.join(newloc, os.path.basename(self.dbpath))
        opath = self.dbpath
        self.conn.close()
        self.library_path, self.dbpath = newloc, dbpath
        self.connect()
        try:
            os.unlink(opath)
        except:
            pass
        for dir in old_dirs:
            try:
                shutil.rmtree(dir)
            except:
                pass

    def __iter__(self):
        for record in self.data._data:
            if record is not None:
                yield record

    def all_ids(self):
        x = self.FIELD_MAP['id']
        for i in iter(self):
            yield i[x]

    def get_data_as_dict(self, prefix=None, authors_as_string=False, ids=None):
        '''
        Return all metadata stored in the database as a dict. Includes paths to
        the cover and each format.

        :param prefix: The prefix for all paths. By default, the prefix is the absolute path
        to the library folder.
        :param ids: Set of ids to return the data for. If None return data for
        all entries in database.
        '''
        if prefix is None:
            prefix = self.library_path
        FIELDS = set(['title', 'authors', 'author_sort', 'publisher', 'rating',
            'timestamp', 'size', 'tags', 'comments', 'series', 'series_index',
            'isbn', 'uuid', 'pubdate'])
        for x in self.custom_column_num_map:
            FIELDS.add(x)
        data = []
        for record in self.data:
            if record is None: continue
            db_id = record[self.FIELD_MAP['id']]
            if ids is not None and db_id not in ids:
                continue
            x = {}
            for field in FIELDS:
                x[field] = record[self.FIELD_MAP[field]]
            data.append(x)
            x['id'] = db_id
            x['formats'] = []
            if not x['authors']:
                x['authors'] = _('Unknown')
            x['authors'] = [i.replace('|', ',') for i in x['authors'].split(',')]
            if authors_as_string:
                x['authors'] = authors_to_string(x['authors'])
            x['tags'] = [i.replace('|', ',').strip() for i in x['tags'].split(',')] if x['tags'] else []
            path = os.path.join(prefix, self.path(record[self.FIELD_MAP['id']], index_is_id=True))
            x['cover'] = os.path.join(path, 'cover.jpg')
            if not self.has_cover(x['id'], index_is_id=True):
                x['cover'] = None
            formats = self.formats(record[self.FIELD_MAP['id']], index_is_id=True)
            if formats:
                for fmt in formats.split(','):
                    path = self.format_abspath(x['id'], fmt, index_is_id=True)
                    if path is None:
                        continue
                    if prefix != self.library_path:
                        path = os.path.relpath(path, self.library_path)
                        path = os.path.join(prefix, path)
                    x['formats'].append(path)
                    x['fmt_'+fmt.lower()] = path
                x['available_formats'] = [i.upper() for i in formats.split(',')]

        return data

    def migrate_old(self, db, progress):
        from PyQt4.QtCore import QCoreApplication
        header = _(u'<p>Migrating old database to ebook library in %s<br><center>')%self.library_path
        progress.setValue(0)
        progress.setLabelText(header)
        QCoreApplication.processEvents()
        db.conn.row_factory = lambda cursor, row : tuple(row)
        db.conn.text_factory = lambda x : unicode(x, 'utf-8', 'replace')
        books = db.conn.get('SELECT id, title, sort, timestamp, series_index, author_sort, isbn FROM books ORDER BY id ASC')
        progress.setAutoReset(False)
        progress.setRange(0, len(books))

        for book in books:
            self.conn.execute('INSERT INTO books(id, title, sort, timestamp, series_index, author_sort, isbn) VALUES(?, ?, ?, ?, ?, ?, ?, ?);', book)

        tables = '''
authors  ratings      tags    series    books_tags_link
comments               publishers
books_authors_link     conversion_options
books_publishers_link
books_ratings_link
books_series_link      feeds
'''.split()
        for table in tables:
            rows = db.conn.get('SELECT * FROM %s ORDER BY id ASC'%table)
            for row in rows:
                self.conn.execute('INSERT INTO %s VALUES(%s)'%(table, ','.join(repeat('?', len(row)))), row)

        self.conn.commit()
        self.refresh('timestamp', True)
        for i, book in enumerate(books):
            progress.setLabelText(header+_(u'Copying <b>%s</b>')%book[1])
            id = book[0]
            self.set_path(id, True)
            formats = db.formats(id, index_is_id=True)
            if not formats:
                formats = []
            else:
                formats = formats.split(',')
            for format in formats:
                data = db.format(id, format, index_is_id=True)
                if data:
                    self.add_format(id, format, cStringIO.StringIO(data), index_is_id=True)
            cover = db.cover(id, index_is_id=True)
            if cover:
                self.set_cover(id, cover)
            progress.setValue(i+1)
        self.conn.commit()
        progress.setLabelText(_('Compacting database'))
        self.vacuum()
        progress.reset()
        return len(books)

    def find_books_in_directory(self, dirpath, single_book_per_directory):
        dirpath = os.path.abspath(dirpath)
        if single_book_per_directory:
            formats = []
            for path in os.listdir(dirpath):
                path = os.path.abspath(os.path.join(dirpath, path))
                if os.path.isdir(path) or not os.access(path, os.R_OK):
                    continue
                ext = os.path.splitext(path)[1]
                if not ext:
                    continue
                ext = ext[1:].lower()
                if ext not in BOOK_EXTENSIONS and ext != 'opf':
                    continue
                formats.append(path)
            yield formats
        else:
            books = {}
            for path in os.listdir(dirpath):
                path = os.path.abspath(os.path.join(dirpath, path))
                if os.path.isdir(path) or not os.access(path, os.R_OK):
                    continue
                ext = os.path.splitext(path)[1]
                if not ext:
                    continue
                ext = ext[1:].lower()
                if ext not in BOOK_EXTENSIONS:
                    continue

                key = os.path.splitext(path)[0]
                if not books.has_key(key):
                    books[key] = []
                books[key].append(path)

            for formats in books.values():
                yield formats

    def import_book_directory_multiple(self, dirpath, callback=None):
        duplicates = []
        for formats in self.find_books_in_directory(dirpath, False):
            mi = metadata_from_formats(formats)
            if mi.title is None:
                continue
            if self.has_book(mi):
                duplicates.append((mi, formats))
                continue
            self.import_book(mi, formats)
            if callable(callback):
                if callback(mi.title):
                    break
        return duplicates

    def import_book_directory(self, dirpath, callback=None):
        dirpath = os.path.abspath(dirpath)
        formats = self.find_books_in_directory(dirpath, True)
        formats = list(formats)[0]
        if not formats:
            return
        mi = metadata_from_formats(formats)
        if mi.title is None:
            return
        if self.has_book(mi):
            return [(mi, formats)]
        self.import_book(mi, formats)
        if callable(callback):
            callback(mi.title)

    def recursive_import(self, root, single_book_per_directory=True, callback=None):
        root = os.path.abspath(root)
        duplicates  = []
        for dirpath in os.walk(root):
            res = self.import_book_directory(dirpath[0], callback=callback) if \
                single_book_per_directory else \
                  self.import_book_directory_multiple(dirpath[0], callback=callback)
            if res is not None:
                duplicates.extend(res)
            if callable(callback):
                if callback(''):
                    break

        return duplicates

    def get_custom_recipes(self):
        for id, title, script in self.conn.get('SELECT id,title,script FROM feeds'):
            yield id, title, script


    def check_integrity(self, callback):
        callback(0., _('Checking SQL integrity...'))
        self.clean()
        user_version = self.user_version
        sql = '\n'.join(self.conn.dump())
        self.conn.close()
        dest = self.dbpath+'.tmp'
        if os.path.exists(dest):
            os.remove(dest)
        conn = None
        try:
            ndb = DBThread(dest, None)
            ndb.connect()
            conn = ndb.conn
            conn.execute('create table temp_sequence(id INTEGER PRIMARY KEY AUTOINCREMENT)')
            conn.commit()
            conn.executescript(sql)
            conn.commit()
            conn.execute('pragma user_version=%d'%user_version)
            conn.commit()
            conn.execute('drop table temp_sequence')
            conn.commit()
            conn.close()
        except:
            if conn is not None:
                try:
                    conn.close()
                except:
                    pass
            if os.path.exists(dest):
                os.remove(dest)
            raise
        else:
            os.remove(self.dbpath)
            shutil.copyfile(dest, self.dbpath)
            self.connect()
            self.field_metadata.remove_dynamic_categories()
            self.field_metadata.remove_custom_fields()
            self.initialize_dynamic()
            self.refresh()
        if os.path.exists(dest):
            os.remove(dest)
        callback(0.1, _('Checking for missing files.'))
        bad = {}
        us = self.data.universal_set()
        total = float(len(us))
        for i, id in enumerate(us):
            formats = self.data.get(id, self.FIELD_MAP['formats'], row_is_id=True)
            if not formats:
                formats = []
            else:
                formats = [x.lower() for x in formats.split(',')]
            actual_formats = self.formats(id, index_is_id=True)
            if not actual_formats:
                actual_formats = []
            else:
                actual_formats = [x.lower() for x in actual_formats.split(',')]

            for fmt in formats:
                if fmt in actual_formats:
                    continue
                if id not in bad:
                    bad[id] = []
                bad[id].append(fmt)
            callback(0.1+0.9*(1+i)/total, _('Checked id') + ' %d'%id)

        for id in bad:
            for fmt in bad[id]:
                self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, fmt.upper()))
        self.conn.commit()
        self.refresh_ids(list(bad.keys()))

        return bad
