'''
Created on 25 May 2010

@author: charles
'''

from calibre.utils.ordered_dict import OrderedDict
from calibre.utils.config import tweaks

class TagsIcons(dict):
    '''
    If the client wants icons to be in the tag structure, this class must be
    instantiated and filled in with real icons. If this class is instantiated
    and passed to get_categories, All items must be given a value not None
    '''

    category_icons = ['authors', 'series', 'formats', 'publisher', 'rating',
                      'news',    'tags',   ':custom', ':user',     'search',]
    def __init__(self, icon_dict):
        for a in self.category_icons:
            if a not in icon_dict:
                raise ValueError('Missing category icon [%s]'%a)
            self[a] = icon_dict[a]

class FieldMetadata(dict):
    '''
    key: the key to the dictionary is:
    - for standard fields, the metadata field name.
    - for custom fields, the metadata field name prefixed by '#'
    This is done to create two 'namespaces' so the names don't clash

    label: the actual column label. No prefixing.

    datatype: the type of information in the field. Valid values are listed in
    VALID_DATA_TYPES below.
    is_multiple: valid for the text datatype. If None, the field is to be
    treated as a single term. If not None, it contains a string, and the field
    is assumed to contain a list of terms separated by that string

    kind == field: is a db field.
    kind == category: standard tag category that isn't a field. see news.
    kind == user: user-defined tag category.
    kind == search: saved-searches category.

    is_category: is a tag browser category. If true, then:
       table: name of the db table used to construct item list
       column: name of the column in the normalized table to join on
       link_column: name of the column in the connection table to join on. This
                    key should not be present if there is no link table
       category_sort: the field in the normalized table to sort on. This
                      key must be present if is_category is True
       If these are None, then the category constructor must know how
       to build the item list (e.g., formats, news).
       The order below is the order that the categories will
       appear in the tags pane.

    name: the text that is to be used when displaying the field. Column headings
    in the GUI, etc.

    search_terms: the terms that can be used to identify the field when
    searching. They can be thought of as aliases for metadata keys, but are only
    valid when passed to search().

    is_custom: the field has been added by the user.

    rec_index: the index of the field in the db metadata record.

    '''

    VALID_DATA_TYPES = frozenset([None, 'rating', 'text', 'comments', 'datetime',
                                  'int', 'float', 'bool', 'series', 'composite'])

    # Builtin metadata {{{

    _field_metadata = [
            ('authors',   {'table':'authors',
                           'column':'name',
                           'link_column':'author',
                           'category_sort':'sort',
                           'datatype':'text',
                           'is_multiple':',',
                           'kind':'field',
                           'name':_('Authors'),
                           'search_terms':['authors', 'author'],
                           'is_custom':False,
                           'is_category':True}),
            ('series',    {'table':'series',
                           'column':'name',
                           'link_column':'series',
                           'category_sort':'(title_sort(name))',
                           'datatype':'series',
                           'is_multiple':None,
                           'kind':'field',
                           'name':_('Series'),
                           'search_terms':['series'],
                           'is_custom':False,
                           'is_category':True}),
            ('formats',   {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':',',
                           'kind':'field',
                           'name':_('Formats'),
                           'search_terms':['formats', 'format'],
                           'is_custom':False,
                           'is_category':True}),
            ('publisher', {'table':'publishers',
                           'column':'name',
                           'link_column':'publisher',
                           'category_sort':'name',
                           'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':_('Publishers'),
                           'search_terms':['publisher'],
                           'is_custom':False,
                           'is_category':True}),
            ('rating',    {'table':'ratings',
                           'column':'rating',
                           'link_column':'rating',
                           'category_sort':'rating',
                           'datatype':'rating',
                           'is_multiple':None,
                           'kind':'field',
                           'name':_('Ratings'),
                           'search_terms':['rating'],
                           'is_custom':False,
                           'is_category':True}),
            ('news',      {'table':'news',
                           'column':'name',
                           'category_sort':'name',
                           'datatype':None,
                           'is_multiple':None,
                           'kind':'category',
                           'name':_('News'),
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':True}),
            ('tags',      {'table':'tags',
                           'column':'name',
                           'link_column': 'tag',
                           'category_sort':'name',
                           'datatype':'text',
                           'is_multiple':',',
                           'kind':'field',
                           'name':_('Tags'),
                           'search_terms':['tags', 'tag'],
                           'is_custom':False,
                           'is_category':True}),
            ('author_sort',{'table':None,
                            'column':None,
                            'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':None,
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':False}),
            ('comments',  {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':None,
                           'search_terms':['comments', 'comment'],
                           'is_custom':False, 'is_category':False}),
            ('cover',     {'table':None,
                           'column':None,
                           'datatype':None,
                           'is_multiple':None,
                           'kind':'field',
                           'name':None,
                           'search_terms':['cover'],
                           'is_custom':False,
                           'is_category':False}),
            ('flags',     {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':None,
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':False}),
            ('id',        {'table':None,
                           'column':None,
                           'datatype':'int',
                           'is_multiple':None,
                           'kind':'field',
                           'name':None,
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':False}),
            ('isbn',      {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':None,
                           'search_terms':['isbn'],
                           'is_custom':False,
                           'is_category':False}),
            ('lccn',      {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':None,
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':False}),
            ('all_metadata',{'table':None,
                             'column':None,
                             'datatype':None,
                             'is_multiple':None,
                             'kind':'field',
                             'name':None,
                             'search_terms':[],
                             'is_custom':False,
                             'is_category':False}),
            ('ondevice',  {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':_('On Device'),
                           'search_terms':['ondevice'],
                           'is_custom':False,
                           'is_category':False}),
            ('path',      {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':None,
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':False}),
            ('pubdate',   {'table':None,
                           'column':None,
                           'datatype':'datetime',
                           'is_multiple':None,
                           'kind':'field',
                           'name':_('Published'),
                           'search_terms':['pubdate'],
                           'is_custom':False,
                           'is_category':False}),
            ('series_index',{'table':None,
                             'column':None,
                             'datatype':'float',
                             'is_multiple':None,
                             'kind':'field',
                             'name':None,
                             'search_terms':['series_index'],
                             'is_custom':False,
                             'is_category':False}),
            ('sort',      {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':None,
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':False}),
            ('size',      {'table':None,
                           'column':None,
                           'datatype':'float',
                           'is_multiple':None,
                           'kind':'field',
                           'name':_('Size (MB)'),
                           'search_terms':['size'],
                           'is_custom':False,
                           'is_category':False}),
            ('timestamp', {'table':None,
                           'column':None,
                           'datatype':'datetime',
                           'is_multiple':None,
                           'kind':'field',
                           'name':_('Date'),
                           'search_terms':['date'],
                           'is_custom':False,
                           'is_category':False}),
            ('title',     {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':_('Title'),
                           'search_terms':['title'],
                           'is_custom':False,
                           'is_category':False}),
            ('uuid',      {'table':None,
                           'column':None,
                           'datatype':'text',
                           'is_multiple':None,
                           'kind':'field',
                           'name':None,
                           'search_terms':[],
                           'is_custom':False,
                           'is_category':False}),
        ]
    # }}}

    # search labels that are not db columns
    search_items = [    'all',
                        'search',
                    ]

    def __init__(self):
        self._tb_cats = OrderedDict()
        self._search_term_map = {}
        self.custom_label_to_key_map = {}
        for k,v in self._field_metadata:
            if v['kind'] == 'field' and v['datatype'] not in self.VALID_DATA_TYPES:
                raise ValueError('Unknown datatype %s for field %s'%(v['datatype'], k))
            self._tb_cats[k] = v
            self._tb_cats[k]['label'] = k
            self._tb_cats[k]['display'] = {}
            self._tb_cats[k]['is_editable'] = True
            self._add_search_terms_to_map(k, v['search_terms'])
        self._tb_cats['timestamp']['display'] = {
                        'date_format': tweaks['gui_timestamp_display_format']}
        self._tb_cats['pubdate']['display'] = {
                        'date_format': tweaks['gui_pubdate_display_format']}
        self.custom_field_prefix = '#'
        self.get = self._tb_cats.get

    def __getitem__(self, key):
        return self._tb_cats[key]

    def __setitem__(self, key, val):
        raise AttributeError('Assigning to this object is forbidden')

    def __delitem__(self, key):
        del self._tb_cats[key]

    def __iter__(self):
        for key in self._tb_cats:
            yield key

    def __contains__(self, key):
        return self.has_key(key)

    def has_key(self, key):
        return key in self._tb_cats

    def keys(self):
        return self._tb_cats.keys()

    def sortable_keys(self):
        return [k for k in self._tb_cats.keys()
                if self._tb_cats[k]['kind']=='field' and
                   self._tb_cats[k]['datatype'] is not None]

    def iterkeys(self):
        for key in self._tb_cats:
            yield key

    def itervalues(self):
        return self._tb_cats.itervalues()

    def values(self):
        return self._tb_cats.values()

    def iteritems(self):
        for key in self._tb_cats:
            yield (key, self._tb_cats[key])

    def items(self):
        return list(self.iteritems())

    def is_custom_field(self, key):
        return key.startswith(self.custom_field_prefix)

    def key_to_label(self, key):
        if 'label' not in self._tb_cats[key]:
            return key
        return self._tb_cats[key]['label']

    def label_to_key(self, label, prefer_custom=False):
        if prefer_custom:
            if label in self.custom_label_to_key_map:
                return self.custom_label_to_key_map[label]
        if 'label' in self._tb_cats:
            return label
        if not prefer_custom:
            if label in self.custom_label_to_key_map:
                return self.custom_label_to_key_map[label]
        raise ValueError('Unknown key [%s]'%(label))

    def get_custom_fields(self):
        return [l for l in self._tb_cats if self._tb_cats[l]['is_custom']]

    def all_metadata(self):
        l = {}
        for k in self._tb_cats:
            l[k] = self._tb_cats[k]
        return l

    def get_custom_field_metadata(self):
        l = {}
        for k in self._tb_cats:
            if self._tb_cats[k]['is_custom']:
                l[k] = self._tb_cats[k]
        return l

    def add_custom_field(self, label, table, column, datatype, colnum, name,
                               display, is_editable, is_multiple, is_category):
        key = self.custom_field_prefix + label
        if key in self._tb_cats:
            raise ValueError('Duplicate custom field [%s]'%(label))
        if datatype not in self.VALID_DATA_TYPES:
            raise ValueError('Unknown datatype %s for field %s'%(datatype, key))
        self._tb_cats[key] = {'table':table,       'column':column,
                             'datatype':datatype,  'is_multiple':is_multiple,
                             'kind':'field',       'name':name,
                             'search_terms':[key], 'label':label,
                             'colnum':colnum,      'display':display,
                             'is_custom':True,     'is_category':is_category,
                             'link_column':'value','category_sort':'value',
                             'is_editable': is_editable,}
        self._add_search_terms_to_map(key, [key])
        self.custom_label_to_key_map[label] = key
        if datatype == 'series':
            key += '_index'
            self._tb_cats[key] = {'table':None,        'column':None,
                                 'datatype':'float',   'is_multiple':None,
                                 'kind':'field',       'name':'',
                                 'search_terms':[key], 'label':label+'_index',
                                 'colnum':None,        'display':{},
                                 'is_custom':False,    'is_category':False,
                                 'link_column':None,   'category_sort':None,
                                 'is_editable': False,}
            self._add_search_terms_to_map(key, [key])
            self.custom_label_to_key_map[label+'_index'] = key

    def remove_dynamic_categories(self):
        for key in list(self._tb_cats.keys()):
            val = self._tb_cats[key]
            if val['is_category'] and val['kind'] in ('user', 'search'):
                del self._tb_cats[key]

    def cc_series_index_column_for(self, key):
        return self._tb_cats[key]['rec_index'] + 1

    def add_user_category(self, label, name):
        if label in self._tb_cats:
            raise ValueError('Duplicate user field [%s]'%(label))
        self._tb_cats[label] = {'table':None,        'column':None,
                                'datatype':None,     'is_multiple':None,
                                'kind':'user',       'name':name,
                                'search_terms':[],    'is_custom':False,
                                'is_category':True}

    def add_search_category(self, label, name):
        if label in self._tb_cats:
            raise ValueError('Duplicate user field [%s]'%(label))
        self._tb_cats[label] = {'table':None,        'column':None,
                                'datatype':None,     'is_multiple':None,
                                'kind':'search',     'name':name,
                                'search_terms':[],    'is_custom':False,
                                'is_category':True}

    def set_field_record_index(self, label, index, prefer_custom=False):
        if prefer_custom:
            key = self.custom_field_prefix+label
            if key not in self._tb_cats:
                key = label
        else:
            if label in self._tb_cats:
                key = label
            else:
                key = self.custom_field_prefix+label
        self._tb_cats[key]['rec_index'] = index  # let the exception fly ...


#    DEFAULT_LOCATIONS = frozenset([
#        'all',
#        'author',       # compatibility
#        'authors',
#        'comment',      # compatibility
#        'comments',
#        'cover',
#        'date',
#        'format',       # compatibility
#        'formats',
#        'isbn',
#        'ondevice',
#        'pubdate',
#        'publisher',
#        'search',
#        'series',
#        'rating',
#        'tag',          # compatibility
#        'tags',
#        'title',
#                 ])

    def get_search_terms(self):
        s_keys = sorted(self._search_term_map.keys())
        for v in self.search_items:
            s_keys.append(v)
#        if set(s_keys) != self.DEFAULT_LOCATIONS:
#            print 'search labels and default_locations do not match:'
#            print set(s_keys) ^ self.DEFAULT_LOCATIONS
        return s_keys

    def _add_search_terms_to_map(self, key, terms):
        if terms is not None:
            for t in terms:
                t = t.lower()
                if t in self._search_term_map:
                    raise ValueError('Attempt to add duplicate search term "%s"'%t)
                self._search_term_map[t] = key

    def search_term_to_key(self, term):
        if term in self._search_term_map:
            return  self._search_term_map[term]
        return term
