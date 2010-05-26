#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import collections, glob, os, re, itertools, functools
from itertools import repeat
from datetime import timedelta

from PyQt4.QtCore import QThread, QReadWriteLock
from PyQt4.QtGui import QImage

from calibre.utils.config import tweaks
from calibre.utils.date import parse_date, now, UNDEFINED_DATE
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.utils.pyparsing import ParseException
# from calibre.library.field_metadata import FieldMetadata

class CoverCache(QThread):

    def __init__(self, library_path, parent=None):
        QThread.__init__(self, parent)
        self.library_path = library_path
        self.id_map = None
        self.id_map_lock = QReadWriteLock()
        self.load_queue = collections.deque()
        self.load_queue_lock = QReadWriteLock(QReadWriteLock.Recursive)
        self.cache = {}
        self.cache_lock = QReadWriteLock()
        self.id_map_stale = True
        self.keep_running = True

    def build_id_map(self):
        self.id_map_lock.lockForWrite()
        self.id_map = {}
        for f in glob.glob(os.path.join(self.library_path, '*', '* (*)', 'cover.jpg')):
            c = os.path.basename(os.path.dirname(f))
            try:
                id = int(re.search(r'\((\d+)\)', c[c.rindex('('):]).group(1))
                self.id_map[id] = f
            except:
                continue
        self.id_map_lock.unlock()
        self.id_map_stale = False


    def set_cache(self, ids):
        self.cache_lock.lockForWrite()
        already_loaded = set([])
        for id in self.cache.keys():
            if id in ids:
                already_loaded.add(id)
            else:
                self.cache.pop(id)
        self.cache_lock.unlock()
        ids = [i for i in ids if i not in already_loaded]
        self.load_queue_lock.lockForWrite()
        self.load_queue = collections.deque(ids)
        self.load_queue_lock.unlock()


    def run(self):
        while self.keep_running:
            if self.id_map is None or self.id_map_stale:
                self.build_id_map()
            while True: # Load images from the load queue
                self.load_queue_lock.lockForWrite()
                try:
                    id = self.load_queue.popleft()
                except IndexError:
                    break
                finally:
                    self.load_queue_lock.unlock()

                self.cache_lock.lockForRead()
                need = True
                if id in self.cache.keys():
                    need = False
                self.cache_lock.unlock()
                if not need:
                    continue
                path = None
                self.id_map_lock.lockForRead()
                if id in self.id_map.keys():
                    path = self.id_map[id]
                else:
                    self.id_map_stale = True
                self.id_map_lock.unlock()
                if path and os.access(path, os.R_OK):
                    try:
                        img = QImage()
                        data = open(path, 'rb').read()
                        img.loadFromData(data)
                        if img.isNull():
                            continue
                    except:
                        continue
                    self.cache_lock.lockForWrite()
                    self.cache[id] = img
                    self.cache_lock.unlock()

            self.sleep(1)

    def stop(self):
        self.keep_running = False

    def cover(self, id):
        val = None
        if self.cache_lock.tryLockForRead(50):
            val = self.cache.get(id, None)
            self.cache_lock.unlock()
        return val

    def clear_cache(self):
        self.cache_lock.lockForWrite()
        self.cache = {}
        self.cache_lock.unlock()

    def refresh(self, ids):
        self.cache_lock.lockForWrite()
        for id in ids:
            self.cache.pop(id, None)
        self.cache_lock.unlock()
        self.load_queue_lock.lockForWrite()
        for id in ids:
            self.load_queue.appendleft(id)
        self.load_queue_lock.unlock()

### Global utility function for get_match here and in gui2/library.py
CONTAINS_MATCH = 0
EQUALS_MATCH   = 1
REGEXP_MATCH   = 2
def _match(query, value, matchkind):
    for t in value:
        t = t.lower()
        try:     ### ignore regexp exceptions, required because search-ahead tries before typing is finished
            if ((matchkind == EQUALS_MATCH and query == t) or
                (matchkind == REGEXP_MATCH and re.search(query, t, re.I)) or ### search unanchored
                (matchkind == CONTAINS_MATCH and query in t)):
                    return True
        except re.error:
            pass
    return False

class ResultCache(SearchQueryParser):

    '''
    Stores sorted and filtered metadata in memory.
    '''
    def __init__(self, FIELD_MAP, cc_label_map, tag_browser_categories):
        self.FIELD_MAP = FIELD_MAP
        self.custom_column_label_map = cc_label_map
        self._map = self._map_filtered = self._data = []
        self.first_sort = True
        self.search_restriction = ''
        self.tag_browser_categories = tag_browser_categories
        self.all_search_locations = tag_browser_categories.get_search_labels()
        SearchQueryParser.__init__(self, self.all_search_locations)
        self.build_date_relop_dict()
        self.build_numeric_relop_dict()

    def __getitem__(self, row):
        return self._data[self._map_filtered[row]]

    def __len__(self):
        return len(self._map_filtered)

    def __iter__(self):
        for id in self._map_filtered:
            yield self._data[id]

    def iterall(self):
        for x in self._data:
            if x is not None:
                yield x

    def iterallids(self):
        idx = self.FIELD_MAP['id']
        for x in self.iterall():
            yield x[idx]

    def universal_set(self):
        return set([i[0] for i in self._data if i is not None])

    def build_date_relop_dict(self):
        '''
        Because the database dates have time in them, we can't use direct
        comparisons even when field_count == 3. The query has time = 0, but
        the database object has time == something. As such, a complete compare
        will almost never be correct.
        '''
        def relop_eq(db, query, field_count):
            if db.year == query.year:
                if field_count == 1:
                    return True
                if db.month == query.month:
                    if field_count == 2:
                        return True
                    return db.day == query.day
            return False

        def relop_gt(db, query, field_count):
            if db.year > query.year:
                return True
            if field_count > 1 and db.year == query.year:
                if db.month > query.month:
                    return True
                return field_count == 3 and db.month == query.month and db.day > query.day
            return False

        def relop_lt(db, query, field_count):
            if db.year < query.year:
                return True
            if field_count > 1 and db.year == query.year:
                if db.month < query.month:
                    return True
                return field_count == 3 and db.month == query.month and db.day < query.day
            return False

        def relop_ne(db, query, field_count):
            return not relop_eq(db, query, field_count)

        def relop_ge(db, query, field_count):
            return not relop_lt(db, query, field_count)

        def relop_le(db, query, field_count):
            return not relop_gt(db, query, field_count)

        self.date_search_relops = {
                            '=' :[1, relop_eq],
                            '>' :[1, relop_gt],
                            '<' :[1, relop_lt],
                            '!=':[2, relop_ne],
                            '>=':[2, relop_ge],
                            '<=':[2, relop_le]
                        }

    def get_dates_matches(self, location, query):
        matches = set([])
        if len(query) < 2:
            return matches
        relop = None
        for k in self.date_search_relops.keys():
            if query.startswith(k):
                (p, relop) = self.date_search_relops[k]
                query = query[p:]
        if relop is None:
                (p, relop) = self.date_search_relops['=']
        if location in self.custom_column_label_map:
            loc = self.FIELD_MAP[self.custom_column_label_map[location]['num']]
        else:
            loc = self.FIELD_MAP[{'date':'timestamp', 'pubdate':'pubdate'}[location]]

        if query == _('today'):
            qd = now()
            field_count = 3
        elif query == _('yesterday'):
            qd = now() - timedelta(1)
            field_count = 3
        elif query == _('thismonth'):
            qd = now()
            field_count = 2
        elif query.endswith(_('daysago')):
            num = query[0:-len(_('daysago'))]
            try:
                qd = now() - timedelta(int(num))
            except:
                raise ParseException(query, len(query), 'Number conversion error', self)
            field_count = 3
        else:
            try:
                qd = parse_date(query)
            except:
                raise ParseException(query, len(query), 'Date conversion error', self)
            if '-' in query:
                field_count = query.count('-') + 1
            else:
                field_count = query.count('/') + 1
        for item in self._data:
            if item is None or item[loc] is None: continue
            if relop(item[loc], qd, field_count):
                matches.add(item[0])
        return matches

    def build_numeric_relop_dict(self):
        self.numeric_search_relops = {
                        '=':[1, lambda r, q: r == q],
                        '>':[1, lambda r, q: r > q],
                        '<':[1, lambda r, q: r < q],
                        '!=':[2, lambda r, q: r != q],
                        '>=':[2, lambda r, q: r >= q],
                        '<=':[2, lambda r, q: r <= q]
                    }

    def get_numeric_matches(self, location, query):
        matches = set([])
        if len(query) == 0:
            return matches
        if query == 'false':
            query = '0'
        elif query == 'true':
            query = '>0'
        relop = None
        for k in self.numeric_search_relops.keys():
            if query.startswith(k):
                (p, relop) = self.numeric_search_relops[k]
                query = query[p:]
        if relop is None:
                (p, relop) = self.numeric_search_relops['=']
        if location in self.custom_column_label_map:
            loc = self.FIELD_MAP[self.custom_column_label_map[location]['num']]
            dt = self.custom_column_label_map[location]['datatype']
            if dt == 'int':
                cast = (lambda x: int (x))
                adjust = lambda x: x
            elif  dt == 'rating':
                cast = (lambda x: int (x))
                adjust = lambda x: x/2
            elif dt == 'float':
                cast = lambda x : float (x)
                adjust = lambda x: x
        else:
            loc = self.FIELD_MAP['rating']
            cast = (lambda x: int (x))
            adjust = lambda x: x/2

        try:
            q = cast(query)
        except:
            return matches

        for item in self._data:
            if item is None:
                continue
            if not item[loc]:
                i = 0
            else:
                i = adjust(item[loc])
            if relop(i, q):
                matches.add(item[0])
        return matches

    def get_matches(self, location, query):
        matches = set([])
        if query and query.strip():
            location = location.lower().strip()

            ### take care of dates special case
            if (location in ('pubdate', 'date')) or \
                    ((location in self.custom_column_label_map) and \
                     self.custom_column_label_map[location]['datatype'] == 'datetime'):
                return self.get_dates_matches(location, query.lower())

            ### take care of numerics special case
            if location == 'rating' or \
                    (location in self.custom_column_label_map and
                     self.custom_column_label_map[location]['datatype'] in
                                ('rating', 'int', 'float')):
                return self.get_numeric_matches(location, query.lower())

            ### everything else
            matchkind = CONTAINS_MATCH
            if (len(query) > 1):
                if query.startswith('\\'):
                    query = query[1:]
                elif query.startswith('='):
                    matchkind = EQUALS_MATCH
                    query = query[1:]
                elif query.startswith('~'):
                    matchkind = REGEXP_MATCH
                    query = query[1:]
            if matchkind != REGEXP_MATCH: ### leave case in regexps because it can be significant e.g. \S \W \D
                query = query.lower()

            if not isinstance(query, unicode):
                query = query.decode('utf-8')
            if location in ('tag', 'author', 'format', 'comment'):
                location += 's'

            MAP = {}
            # Fields not used when matching against text contents. These are
            # the non-text fields
            EXCLUDE_FIELDS = []

            # get the db columns for the standard searchables
            for x in self.tag_browser_categories:
                if len(self.tag_browser_categories[x]['search_labels']) and \
                         not self.tag_browser_categories.is_custom_field(x):
                    MAP[x] = self.tag_browser_categories[x]['rec_index']
                    if self.tag_browser_categories[x]['datatype'] != 'text':
                        EXCLUDE_FIELDS.append(MAP[x])

            # add custom columns to MAP. Put the column's type into IS_CUSTOM
            IS_CUSTOM = []
            for x in range(len(self.FIELD_MAP)):
                IS_CUSTOM.append('')
            # normal and custom ratings columns use the same code
            IS_CUSTOM[self.FIELD_MAP['rating']] = 'rating'
            for x in self.tag_browser_categories.get_custom_fields():
                if self.tag_browser_categories[x]['datatype'] != "datetime":
                    MAP[x] = self.FIELD_MAP[self.tag_browser_categories[x]['colnum']]
                    IS_CUSTOM[MAP[x]] = self.tag_browser_categories[x]['datatype']

            SPLITABLE_FIELDS = [MAP['authors'], MAP['tags'], MAP['formats']]
            for x in self.tag_browser_categories.get_custom_fields():
                if self.tag_browser_categories[x]['is_multiple']:
                    SPLITABLE_FIELDS.append(MAP[x])

            try:
                rating_query = int(query) * 2
            except:
                rating_query = None

            location = [location] if location != 'all' else list(MAP.keys())
            for i, loc in enumerate(location):
                location[i] = MAP[loc]

            # get the tweak here so that the string lookup and compare aren't in the loop
            bools_are_tristate = tweaks['bool_custom_columns_are_tristate'] == 'yes'

            for loc in location:
                if loc == MAP['authors']:
                    ### DB stores authors with commas changed to bars, so change query
                    q = query.replace(',', '|');
                else:
                    q = query

                for item in self._data:
                    if item is None: continue

                    if IS_CUSTOM[loc] == 'bool': # complexity caused by the two-/three-value tweak
                        v = item[loc]
                        if not bools_are_tristate:
                            if v is None or not v: # item is None or set to false
                                if q in [_('no'), _('unchecked'), 'false']:
                                    matches.add(item[0])
                            else: # item is explicitly set to true
                                if q in [_('yes'), _('checked'), 'true']:
                                    matches.add(item[0])
                        else:
                            if v is None:
                                if q in [_('empty'), _('blank'), 'false']:
                                    matches.add(item[0])
                            elif not v: # is not None and false
                                if q in [_('no'), _('unchecked'), 'true']:
                                    matches.add(item[0])
                            else: # item is not None and true
                                if q in [_('yes'), _('checked'), 'true']:
                                    matches.add(item[0])
                        continue

                    if not item[loc]:
                        if q == 'false':
                            matches.add(item[0])
                        continue     # item is empty. No possible matches below
                    if q == 'false': # Field has something in it, so a false query does not match
                        continue

                    if q == 'true':
                        if isinstance(item[loc], basestring):
                            if item[loc].strip() == '':
                                continue
                        matches.add(item[0])
                        continue

                    if IS_CUSTOM[loc] == 'rating': # get here if 'all' query
                        if rating_query and rating_query == int(item[loc]):
                            matches.add(item[0])
                        continue

                    try: # a conversion below might fail
                        # relationals not supported in 'all' queries
                        if IS_CUSTOM[loc] == 'float':
                            if float(query) == item[loc]:
                                matches.add(item[0])
                            continue
                        if IS_CUSTOM[loc] == 'int':
                            if int(query) == item[loc]:
                                matches.add(item[0])
                            continue
                    except:
                        # A conversion threw an exception. Because of the type,
                        # no further match is possible
                        continue

                    if loc not in EXCLUDE_FIELDS:
                        if loc in SPLITABLE_FIELDS:
                            if IS_CUSTOM[loc]:
                                vals = item[loc].split('|')
                            else:
                                vals = item[loc].split(',')
                        else:
                            vals = [item[loc]] ### make into list to make _match happy
                        if _match(q, vals, matchkind):
                            matches.add(item[0])
                            continue
        return matches

    def remove(self, id):
        self._data[id] = None
        if id in self._map:
            self._map.remove(id)
        if id in self._map_filtered:
            self._map_filtered.remove(id)

    def set(self, row, col, val, row_is_id=False):
        id = row if row_is_id else self._map_filtered[row]
        self._data[id][col] = val

    def get(self, row, col, row_is_id=False):
        id = row if row_is_id else self._map_filtered[row]
        return self._data[id][col]

    def index(self, id, cache=False):
        x = self._map if cache else self._map_filtered
        return x.index(id)

    def row(self, id):
        return self.index(id)

    def has_id(self, id):
        try:
            return self._data[id] is not None
        except IndexError:
            pass
        return False

    def refresh_ids(self, db, ids):
        '''
        Refresh the data in the cache for books identified by ids.
        Returns a list of affected rows or None if the rows are filtered.
        '''
        for id in ids:
            try:
                self._data[id] = db.conn.get('SELECT * from meta2 WHERE id=?', (id,))[0]
                self._data[id].append(db.has_cover(id, index_is_id=True))
                self._data[id].append(db.book_on_device_string(id))
            except IndexError:
                return None
        try:
            return map(self.row, ids)
        except ValueError:
            pass
        return None

    def books_added(self, ids, db):
        if not ids:
            return
        self._data.extend(repeat(None, max(ids)-len(self._data)+2))
        for id in ids:
            self._data[id] = db.conn.get('SELECT * from meta2 WHERE id=?', (id,))[0]
            self._data[id].append(db.has_cover(id, index_is_id=True))
            self._data[id].append(db.book_on_device_string(id))
        self._map[0:0] = ids
        self._map_filtered[0:0] = ids

    def books_deleted(self, ids):
        for id in ids:
            self._data[id] = None
            if id in self._map: self._map.remove(id)
            if id in self._map_filtered: self._map_filtered.remove(id)

    def count(self):
        return len(self._map)

    def refresh_ondevice(self, db):
        ondevice_col = self.FIELD_MAP['ondevice']
        for item in self._data:
            if item is not None:
                item[ondevice_col] = db.book_on_device_string(item[0])

    def refresh(self, db, field=None, ascending=True):
        temp = db.conn.get('SELECT * FROM meta2')
        self._data = list(itertools.repeat(None, temp[-1][0]+2)) if temp else []
        for r in temp:
            self._data[r[0]] = r
        for item in self._data:
            if item is not None:
                item.append(db.has_cover(item[0], index_is_id=True))
                item.append(db.book_on_device_string(item[0]))
        self._map = [i[0] for i in self._data if i is not None]
        if field is not None:
            self.sort(field, ascending)
        self._map_filtered = list(self._map)

    def seriescmp(self, x, y):
        sidx = self.FIELD_MAP['series']
        try:
            ans = cmp(self._data[x][sidx].lower(), self._data[y][sidx].lower())
        except AttributeError: # Some entries may be None
            ans = cmp(self._data[x][sidx], self._data[y][sidx])
        if ans != 0: return ans
        sidx = self.FIELD_MAP['series_index']
        return cmp(self._data[x][sidx], self._data[y][sidx])

    def cmp(self, loc, x, y, asstr=True, subsort=False):
        try:
            ans = cmp(self._data[x][loc].lower(), self._data[y][loc].lower()) if \
                asstr else cmp(self._data[x][loc], self._data[y][loc])
        except AttributeError: # Some entries may be None
            ans = cmp(self._data[x][loc], self._data[y][loc])
        except TypeError: ## raised when a datetime is None
            x = self._data[x][loc]
            if x is None:
                x = UNDEFINED_DATE
            y = self._data[y][loc]
            if y is None:
                y = UNDEFINED_DATE
            return cmp(x, y)
        if subsort and ans == 0:
            return cmp(self._data[x][11].lower(), self._data[y][11].lower())
        return ans

    def sort(self, field, ascending, subsort=False):
        field = field.lower().strip()
        if field in ('author', 'tag', 'comment'):
            field += 's'
        if   field == 'date': field = 'timestamp'
        elif field == 'title': field = 'sort'
        elif field == 'authors': field = 'author_sort'
        as_string = field not in ('size', 'rating', 'timestamp')
        if field in self.custom_column_label_map:
            as_string = self.custom_column_label_map[field]['datatype'] in ('comments', 'text')
            field = self.custom_column_label_map[field]['num']

        if self.first_sort:
            subsort = True
            self.first_sort = False
        fcmp = self.seriescmp if field == 'series' else \
            functools.partial(self.cmp, self.FIELD_MAP[field], subsort=subsort,
                              asstr=as_string)
        self._map.sort(cmp=fcmp, reverse=not ascending)
        self._map_filtered = [id for id in self._map if id in self._map_filtered]

    def search(self, query, return_matches=False,
            ignore_search_restriction=False):
        q = ''
        if not query or not query.strip():
            if not ignore_search_restriction:
                q = self.search_restriction
        else:
            q = query
            if not ignore_search_restriction:
                q = u'%s (%s)' % (self.search_restriction, query)
        if not q:
            if return_matches:
                return list(self._map) # when return_matches, do not update the maps!
            self._map_filtered = list(self._map)
            return
        matches = sorted(self.parse(q))
        ans = [id for id in self._map if id in matches]
        if return_matches:
            return ans
        self._map_filtered = ans

    def set_search_restriction(self, s):
        self.search_restriction = s
