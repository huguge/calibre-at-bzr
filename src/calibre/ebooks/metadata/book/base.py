#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy
import traceback

from calibre import prints
from calibre.ebooks.metadata.book import COPYABLE_METADATA_FIELDS
from calibre.ebooks.metadata.book import STANDARD_METADATA_FIELDS
from calibre.ebooks.metadata.book import TOP_LEVEL_CLASSIFIERS
from calibre.utils.date import isoformat, format_date



NULL_VALUES = {
                'user_metadata': {},
                'cover_data'   : (None, None),
                'tags'         : [],
                'classifiers'  : {},
                'languages'    : [],
                'device_collections': [],
                'author_sort_map': {},
                'authors'      : [_('Unknown')],
                'title'        : _('Unknown'),
                'language'     : 'und'
}

class Metadata(object):

    '''
    A class representing all the metadata for a book.

    Please keep the method based API of this class to a minimum. Every method
    becomes a reserved field name.
    '''

    def __init__(self, title, authors=(_('Unknown'),), other=None):
        '''
        @param title: title or ``_('Unknown')``
        @param authors: List of strings or []
        @param other: None or a metadata object
        '''
        object.__setattr__(self, '_data', copy.deepcopy(NULL_VALUES))
        if other is not None:
            self.smart_update(other)
        else:
            if title:
                self.title = title
            if authors:
                #: List of strings or []
                self.author = list(authors) if authors else []# Needed for backward compatibility
                self.authors = list(authors) if authors else []

    def __getattribute__(self, field):
        _data = object.__getattribute__(self, '_data')
        if field in TOP_LEVEL_CLASSIFIERS:
            return _data.get('classifiers').get(field, None)
        if field in STANDARD_METADATA_FIELDS:
            return _data.get(field, None)
        try:
            return object.__getattribute__(self, field)
        except AttributeError:
            pass
        if field in _data['user_metadata'].iterkeys():
            return _data['user_metadata'][field]['#value#']
        raise AttributeError(
                'Metadata object has no attribute named: '+ repr(field))

    def __setattr__(self, field, val, extra=None):
        _data = object.__getattribute__(self, '_data')
        if field in TOP_LEVEL_CLASSIFIERS:
            _data['classifiers'].update({field: val})
        elif field in STANDARD_METADATA_FIELDS:
            if val is None:
                val = NULL_VALUES.get(field, None)
            _data[field] = val
        elif field in _data['user_metadata'].iterkeys():
            _data['user_metadata'][field]['#value#'] = val
            _data['user_metadata'][field]['#extra#'] = extra
        else:
            # You are allowed to stick arbitrary attributes onto this object as
            # long as they don't conflict with global or user metadata names
            # Don't abuse this privilege
            self.__dict__[field] = val

    def get(self, field, default=None):
        if default is not None:
            try:
                return self.__getattribute__(field)
            except AttributeError:
                return default
        return self.__getattribute__(field)

    def get_extra(self, field):
        _data = object.__getattribute__(self, '_data')
        if field in _data['user_metadata'].iterkeys():
            return _data['user_metadata'][field]['#extra#']
        raise AttributeError(
                'Metadata object has no attribute named: '+ repr(field))

    def set(self, field, val, extra=None):
        self.__setattr__(field, val, extra)

    @property
    def user_metadata_keys(self):
        'The set of user metadata names this object knows about'
        _data = object.__getattribute__(self, '_data')
        return frozenset(_data['user_metadata'].iterkeys())

    def get_all_user_metadata(self, make_copy):
        '''
        return a dict containing all the custom field metadata associated with
        the book.
        '''
        _data = object.__getattribute__(self, '_data')
        user_metadata = _data['user_metadata']
        if not make_copy:
            return user_metadata
        res = {}
        for k in user_metadata:
            res[k] = copy.deepcopy(user_metadata[k])
        return res

    def get_user_metadata(self, field, make_copy):
        '''
        return field metadata from the object if it is there. Otherwise return
        None. field is the key name, not the label. Return a copy if requested,
        just in case the user wants to change values in the dict.
        '''
        _data = object.__getattribute__(self, '_data')
        _data = _data['user_metadata']
        if field in _data:
            if make_copy:
                return copy.deepcopy(_data[field])
            return _data[field]
        return None

    def set_all_user_metadata(self, metadata):
        '''
        store custom field metadata into the object. Field is the key name
        not the label
        '''
        if metadata is None:
            traceback.print_stack()
        else:
            for key in metadata:
                self.set_user_metadata(key, metadata[key])

    def set_user_metadata(self, field, metadata):
        '''
        store custom field metadata for one column into the object. Field is
        the key name not the label
        '''
        if field is not None:
            if not field.startswith('#'):
                raise AttributeError(
                        'Custom field name %s must begin with \'#\''%repr(field))
            if metadata is None:
                traceback.print_stack()
                return
            metadata = copy.deepcopy(metadata)
            if '#value#' not in metadata:
                if metadata['datatype'] == 'text' and metadata['is_multiple']:
                    metadata['#value#'] = []
                else:
                    metadata['#value#'] = None
            _data = object.__getattribute__(self, '_data')
            _data['user_metadata'][field] = metadata

    def get_all_non_none_attributes(self):
        '''
        Return a dictionary containing all non-None metadata fields, including
        the custom ones.
        '''
        result = {}
        _data = object.__getattribute__(self, '_data')
        for attr in STANDARD_METADATA_FIELDS:
            v = _data.get(attr, None)
            if v is not None:
                result[attr] = v
        for attr in _data['user_metadata'].iterkeys():
            v = _data['user_metadata'][attr]['#value#']
            if v is not None:
                result[attr] = v
                if _data['user_metadata'][attr]['datatype'] == 'series':
                    result[attr+'_index'] = _data['user_metadata'][attr]['#extra#']
        return result

    # Old Metadata API {{{
    def print_all_attributes(self):
        for x in STANDARD_METADATA_FIELDS:
            prints('%s:'%x, getattr(self, x, 'None'))
        for x in self.user_metadata_keys:
            meta = self.get_user_metadata(x, make_copy=False)
            if meta is not None:
                prints(x, meta)
        prints('--------------')

    def smart_update(self, other, replace_metadata=False):
        '''
        Merge the information in `other` into self. In case of conflicts, the information
        in `other` takes precedence, unless the information in `other` is NULL.
        '''
        def copy_not_none(dest, src, attr):
            v = getattr(src, attr, None)
            if v not in (None, NULL_VALUES.get(attr, None)):
                setattr(dest, attr, copy.deepcopy(v))

        if other.title and other.title != _('Unknown'):
            self.title = other.title
            if hasattr(other, 'title_sort'):
                self.title_sort = other.title_sort

        if other.authors and other.authors[0] != _('Unknown'):
            self.authors = list(other.authors)
            if hasattr(other, 'author_sort_map'):
                self.author_sort_map = dict(other.author_sort_map)
            if hasattr(other, 'author_sort'):
                self.author_sort = other.author_sort

        if replace_metadata:
            SPECIAL_FIELDS = frozenset(['lpath', 'size', 'comments'])
            for attr in COPYABLE_METADATA_FIELDS:
                setattr(self, attr, getattr(other, attr, 1.0 if \
                        attr == 'series_index' else None))
            self.tags = other.tags
            self.cover_data = getattr(other, 'cover_data',
                    NULL_VALUES['cover_data'])
            self.set_all_user_metadata(other.get_all_user_metadata(make_copy=True))
            for x in SPECIAL_FIELDS:
                copy_not_none(self, other, x)
            # language is handled below
        else:
            for attr in COPYABLE_METADATA_FIELDS:
                if hasattr(other, attr):
                    copy_not_none(self, other, attr)
            if other.tags:
                # Case-insensitive but case preserving merging
                lotags = [t.lower() for t in other.tags]
                lstags = [t.lower() for t in self.tags]
                ot, st = map(frozenset, (lotags, lstags))
                for t in st.interection(ot):
                    sidx = lstags.index(t)
                    oidx = lotags.index(t)
                    self.tags[sidx] = other.tags[oidx]
                self.tags += [t for t in other.tags if t.lower() in ot-st]
            if getattr(other, 'cover_data', False):
                other_cover = other.cover_data[-1]
                self_cover = self.cover_data[-1] if self.cover_data else ''
                if not self_cover: self_cover = ''
                if not other_cover: other_cover = ''
                if len(other_cover) > len(self_cover):
                    self.cover_data = other.cover_data
            if getattr(other, 'user_metadata_keys', None):
                for x in other.user_metadata_keys:
                    meta = other.get_user_metadata(x, make_copy=True)
                    if meta is not None:
                        self.set_user_metadata(x, meta) # get... did the deepcopy
            my_comments = getattr(self, 'comments', '')
            other_comments = getattr(other, 'comments', '')
            if not my_comments:
                my_comments = ''
            if not other_comments:
                other_comments = ''
            if len(other_comments.strip()) > len(my_comments.strip()):
                self.comments = other_comments

        other_lang = getattr(other, 'language', None)
        if other_lang and other_lang.lower() != 'und':
            self.language = other_lang

    def format_series_index(self, val=None):
        from calibre.ebooks.metadata import fmt_sidx
        v = self.series_index if val is None else val
        try:
            x = float(v)
        except ValueError:
            x = 1
        return fmt_sidx(x)

    def authors_from_string(self, raw):
        from calibre.ebooks.metadata import string_to_authors
        self.authors = string_to_authors(raw)

    def format_authors(self):
        from calibre.ebooks.metadata import authors_to_string
        return authors_to_string(self.authors)

    def format_tags(self):
        return u', '.join([unicode(t) for t in self.tags])

    def format_rating(self):
        return unicode(self.rating)

    def format_custom_field(self, key):
        '''
        returns the tuple (field_name, formatted_value)
        '''
        cmeta = self.get_user_metadata(key, make_copy=False)
        name = unicode(cmeta['name'])
        res = self.get(key, None)
        if res is not None:
            datatype = cmeta['datatype']
            if datatype == 'text' and cmeta['is_multiple']:
                res = u', '.join(res)
            elif datatype == 'series':
                res = res + ' [%s]'%self.format_series_index(val=self.get_extra(key))
            elif datatype == 'datetime':
                res = format_date(res, cmeta['display'].get('date_format','dd MMM yyyy'))
            elif datatype == 'bool':
                res = _('Yes') if res else _('No')
        return (name, unicode(res))

    def __unicode__(self):
        from calibre.ebooks.metadata import authors_to_string
        ans = []
        def fmt(x, y):
            ans.append(u'%-20s: %s'%(unicode(x), unicode(y)))

        fmt('Title', self.title)
        if self.title_sort:
            fmt('Title sort', self.title_sort)
        if self.authors:
            fmt('Author(s)',  authors_to_string(self.authors) + \
               ((' [' + self.author_sort + ']') if self.author_sort else ''))
        if self.publisher:
            fmt('Publisher', self.publisher)
        if getattr(self, 'book_producer', False):
            fmt('Book Producer', self.book_producer)
        if self.comments:
            fmt('Comments', self.comments)
        if self.isbn:
            fmt('ISBN', self.isbn)
        if self.tags:
            fmt('Tags', u', '.join([unicode(t) for t in self.tags]))
        if self.series:
            fmt('Series', self.series + ' #%s'%self.format_series_index())
        if self.language:
            fmt('Language', self.language)
        if self.rating is not None:
            fmt('Rating', self.rating)
        if self.timestamp is not None:
            fmt('Timestamp', isoformat(self.timestamp))
        if self.pubdate is not None:
            fmt('Published', isoformat(self.pubdate))
        if self.rights is not None:
            fmt('Rights', unicode(self.rights))
        for key in self.user_metadata_keys:
            val = self.get(key, None)
            if val is not None:
                (name, val) = self.format_custom_field(key)
                fmt(name, unicode(val))
        return u'\n'.join(ans)

    def to_html(self):
        from calibre.ebooks.metadata import authors_to_string
        ans = [(_('Title'), unicode(self.title))]
        ans += [(_('Author(s)'), (authors_to_string(self.authors) if self.authors else _('Unknown')))]
        ans += [(_('Publisher'), unicode(self.publisher))]
        ans += [(_('Producer'), unicode(self.book_producer))]
        ans += [(_('Comments'), unicode(self.comments))]
        ans += [('ISBN', unicode(self.isbn))]
        ans += [(_('Tags'), u', '.join([unicode(t) for t in self.tags]))]
        if self.series:
            ans += [(_('Series'), unicode(self.series)+ ' #%s'%self.format_series_index())]
        ans += [(_('Language'), unicode(self.language))]
        if self.timestamp is not None:
            ans += [(_('Timestamp'), unicode(self.timestamp.isoformat(' ')))]
        if self.pubdate is not None:
            ans += [(_('Published'), unicode(self.pubdate.isoformat(' ')))]
        if self.rights is not None:
            ans += [(_('Rights'), unicode(self.rights))]
        for key in self.user_metadata_keys:
            val = self.get(key, None)
            if val is not None:
                (name, val) = self.format_custom_field(key)
                ans += [(name, val)]
        for i, x in enumerate(ans):
            ans[i] = u'<tr><td><b>%s</b></td><td>%s</td></tr>'%x
        return u'<table>%s</table>'%u'\n'.join(ans)

    def __str__(self):
        return self.__unicode__().encode('utf-8')

    def __nonzero__(self):
        return bool(self.title or self.author or self.comments or self.tags)

    # }}}

