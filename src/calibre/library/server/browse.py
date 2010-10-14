#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import operator, os, json
from urllib import quote
from binascii import hexlify

import cherrypy

from calibre.constants import filesystem_encoding
from calibre import isbytestring, force_unicode, prepare_string_for_xml as xml
from calibre.utils.ordered_dict import OrderedDict

def paginate(offsets, content, base_url, up_url=None): # {{{
    'Create markup for pagination'

    if '?' not in base_url:
        base_url += '?'

    if base_url[-1] != '?':
        base_url += '&'

    def navlink(decoration, name, cls, offset):
        label = xml(name)
        if cls in ('next', 'last'):
            label += '&nbsp;' + decoration
        else:
            label = decoration + '&nbsp;' + label
        return (u'<a class="{cls}" href="{base_url}&amp;offset={offset}" title={name}>'
                u'{label}</a>').format(cls=cls, decoration=decoration,
                        name=xml(name, True), offset=offset,
                        base_url=xml(base_url, True), label=label)
    left = ''
    if offsets.offset > 0 and offsets.previous_offset > 0:
        left += navlink(u'\u219e', _('First'), 'first', 0)
    if offsets.offset > 0:
        left += ' ' + navlink('&larr;', _('Previous'), 'previous',
                offsets.previous_offset)

    middle = ''
    if up_url:
        middle = '<a href="{0}" title="{1}">[{1} &uarr;]</a>'.format(xml(up_url, True),
                xml(_('Up')))

    right = ''
    if offsets.next_offset > -1:
        right += navlink('&rarr', _('Next'), 'next', offsets.next_offset)
    if offsets.last_offset > offsets.next_offset and offsets.last_offset > 0:
        right += ' ' + navlink(u'\u21A0', _('Last'), 'last', offsets.last_offset)

    navbar = u'''
            <table class="navbar">
                <tr>
                    <td class="left">{left}</td>
                    <td class="middle">{middle}</td>
                    <td class="right">{right}</td>
                </tr>
            <table>
    '''.format(left=left, right=right, middle=middle)

    templ = u'''
        <div class="page">
            {navbar}
            <div class="page-contents">
            {content}
            </div>
            {navbar}
        </div>
    '''
    return templ.format(navbar=navbar, content=content)
# }}}

def utf8(x): # {{{
    if isinstance(x, unicode):
        x = x.encode('utf-8')
    return x
# }}}

def render_rating(rating, container='span'): # {{{
    if rating < 0.1:
        return '', ''
    added = 0
    rstring = xml(_('Average rating: %.1f stars')% (rating if rating else 0.0),
            True)
    ans = ['<%s class="rating">' % (container)]
    for i in range(5):
        n = rating - added
        x = 'half'
        if n <= 0.1:
            x = 'off'
        elif n >= 0.9:
            x = 'on'
        ans.append(
            u'<img alt="{0}" title="{0}" src="/static/star-{1}.png" />'.format(
                rstring, x))
        added += 1
    ans.append('</%s>'%container)
    return u''.join(ans), rstring

# }}}

def get_category_items(category, items, db, datatype): # {{{

    def item(i):
        templ = (u'<tr title="{4}" class="category-item">'
                '<td><h4>{0}</h4></td><td>{1}</td>'
                '<td>{2}'
                '<span class="href">{3}</span></td></tr>')
        rating, rstring = render_rating(i.avg_rating)
        name = xml(i.name)
        if datatype == 'rating':
            name = xml(_('%d stars')%int(i.avg_rating))
        id_ = i.id
        if id_ is None:
            id_ = hexlify(force_unicode(name).encode('utf-8'))
        id_ = xml(str(id_))
        desc = ''
        if i.count > 0:
            desc += '[' + _('%d items')%i.count + ']'
        href = '/browse/matches/%s/%s'%(category, id_)
        return templ.format(xml(name), rating,
                xml(desc), xml(quote(href)), rstring)

    items = list(map(item, items))
    return '\n'.join(['<table>'] + items + ['</table>'])

# }}}

class Endpoint(object): # {{{
    'Manage encoding, mime-type, last modified, cookies, etc.'

    def __init__(self, mimetype='text/html; charset=utf-8', sort_type='category'):
        self.mimetype = mimetype
        self.sort_type = sort_type
        self.sort_kwarg = sort_type + '_sort'
        self.sort_cookie_name = 'calibre_browse_server_sort_'+self.sort_type

    def __call__(eself, func):

        def do(self, *args, **kwargs):
            sort_val = None
            cookie = cherrypy.request.cookie
            if cookie.has_key(eself.sort_cookie_name):
                sort_val = cookie[eself.sort_cookie_name].value
            kwargs[eself.sort_kwarg] = sort_val

            ans = func(self, *args, **kwargs)
            cherrypy.response.headers['Content-Type'] = eself.mimetype
            updated = self.db.last_modified()
            cherrypy.response.headers['Last-Modified'] = \
                self.last_modified(max(updated, self.build_time))
            ans = utf8(ans)
            return ans

        do.__name__ = func.__name__

        return do
# }}}

class BrowseServer(object):

    def add_routes(self, connect):
        base_href = '/browse'
        connect('browse', base_href, self.browse_catalog)
        connect('browse_catalog', base_href+'/category/{category}',
                self.browse_catalog)
        connect('browse_category_group',
                base_href+'/category_group/{category}/{group}',
                self.browse_category_group)
        connect('browse_list', base_href+'/list/{query}', self.browse_list)
        connect('browse_search', base_href+'/search/{query}',
                self.browse_search)
        connect('browse_book', base_href+'/book/{uuid}', self.browse_book)

    def browse_template(self, sort, category=True):

        def generate():
            scn = 'calibre_browse_server_sort_'

            if category:
                sort_opts = [('rating', _('Average rating')), ('name',
                    _('Name')), ('popularity', _('Popularity'))]
                scn += 'category'
            else:
                scn += 'list'
                fm = self.db.field_metadata
                sort_opts, added = [], set([])
                for x in fm.sortable_field_keys():
                    n = fm[x]['name']
                    if n not in added:
                        added.add(n)
                        sort_opts.append((x, n))

            ans = P('content_server/browse/browse.html',
                    data=True).decode('utf-8')
            ans = ans.replace('{sort_select_label}', xml(_('Sort by')+':'))
            ans = ans.replace('{sort_cookie_name}', scn)
            opts = ['<option %svalue="%s">%s</option>' % (
                'selected="selected" ' if k==sort else '',
                xml(k), xml(n), ) for k, n in
                    sorted(sort_opts, key=operator.itemgetter(1))]
            ans = ans.replace('{sort_select_options}', ('\n'+' '*20).join(opts))
            lp = self.db.library_path
            if isbytestring(lp):
                lp = force_unicode(lp, filesystem_encoding)
            if isinstance(ans, unicode):
                ans = ans.encode('utf-8')
            ans = ans.replace('{library_name}', xml(os.path.basename(lp)))
            ans = ans.replace('{library_path}', xml(lp, True))
            return ans

        if self.opts.develop:
            return generate()
        if not hasattr(self, '__browse_template__'):
            self.__browse_template__ = generate()
        return self.__browse_template__


    # Catalogs {{{
    def browse_toplevel(self):
        categories = self.categories_cache()
        category_meta = self.db.field_metadata
        cats = [
                (_('Newest'), 'newest'),
                ]

        def getter(x):
            return category_meta[x]['name'].lower()

        for category in sorted(categories,
                            cmp=lambda x,y: cmp(getter(x), getter(y))):
            if len(categories[category]) == 0:
                continue
            if category == 'formats':
                continue
            meta = category_meta.get(category, None)
            if meta is None:
                continue
            cats.append((meta['name'], category))
        cats = ['<li title="{2} {0}">{0}<span>/browse/category/{1}</span></li>'\
                .format(xml(x, True), xml(quote(y)), xml(_('Browse books by')))
                for x, y in cats]

        main = '<div class="toplevel"><h3>{0}</h3><ul>{1}</ul></div>'\
                .format(_('Choose a category to browse by:'), '\n\n'.join(cats))
        return self.browse_template('name').format(title='',
                    script='toplevel();', main=main)

    def browse_sort_categories(self, items, sort):
        if sort not in ('rating', 'name', 'popularity'):
            sort = 'name'
        def sorter(x):
            ans = getattr(x, 'sort', x.name)
            if hasattr(ans, 'upper'):
                ans = ans.upper()
            return ans
        items.sort(key=sorter)
        if sort == 'popularity':
            items.sort(key=operator.attrgetter('count'), reverse=True)
        elif sort == 'rating':
            items.sort(key=operator.attrgetter('avg_rating'), reverse=True)
        return sort

    def browse_category(self, category, sort):
        categories = self.categories_cache()
        category_meta = self.db.field_metadata
        category_name = category_meta[category]['name']
        datatype = category_meta[category]['datatype']

        if category not in categories:
            raise cherrypy.HTTPError(404, 'category not found')

        items = categories[category]
        sort = self.browse_sort_categories(items, sort)

        script = 'true'

        if len(items) <= self.opts.max_opds_ungrouped_items:
            script = 'false'
            items = get_category_items(category, items, self.db, datatype)
        else:
            getter = lambda x: unicode(getattr(x, 'sort', x.name))
            starts = set([])
            for x in items:
                val = getter(x)
                if not val:
                    val = u'A'
                starts.add(val[0].upper())
            category_groups = OrderedDict()
            for x in sorted(starts):
                category_groups[x] = len([y for y in items if
                    getter(y).upper().startswith(x)])
            items = [(u'<h3 title="{0}">{0} <span>[{2}]</span></h3><div>'
                      u'<div class="loaded" style="display:none"></div>'
                      u'<div class="loading"><img alt="{1}" src="/static/loading.gif" /><em>{1}</em></div>'
                      u'<span class="load_href">{3}</span></div>').format(
                        xml(s, True),
                        xml(_('Loading, please wait'))+'&hellip;',
                        unicode(c),
                        xml(u'/browse/category_group/%s/%s'%(category, s)))
                    for s, c in category_groups.items()]
            items = '\n\n'.join(items)
            items = u'<div id="groups">\n{0}</div>'.format(items)



        script = 'category(%s);'%script

        main = u'''
            <div class="category">
                <h3>{0}</h3>
                    <a class="navlink" href="/browse"
                        title="{2}">{2}&nbsp;&uarr;</a>
                {1}
            </div>
        '''.format(
                xml(_('Browsing by')+': ' + category_name), items,
                xml(_('Up'), True))

        return self.browse_template(sort).format(title=category_name,
                script=script, main=main)

    @Endpoint(mimetype='application/json; charset=utf-8')
    def browse_category_group(self, category=None, group=None,
            category_sort=None):
        sort = category_sort
        if sort not in ('rating', 'name', 'popularity'):
            sort = 'name'
        categories = self.categories_cache()
        category_meta = self.db.field_metadata
        datatype = category_meta[category]['datatype']

        if category not in categories:
            raise cherrypy.HTTPError(404, 'category not found')
        if not group:
            raise cherrypy.HTTPError(404, 'invalid group')

        items = categories[category]
        entries = []
        getter = lambda x: unicode(getattr(x, 'sort', x.name))
        for x in items:
            val = getter(x)
            if not val:
                val = u'A'
            if val.upper().startswith(group):
                entries.append(x)

        sort = self.browse_sort_categories(entries, sort)
        entries = get_category_items(category, entries, self.db, datatype)
        return json.dumps(entries, ensure_ascii=False)



    @Endpoint()
    def browse_catalog(self, category=None, category_sort=None):
        'Entry point for top-level, categories and sub-categories'
        if category == None:
            ans = self.browse_toplevel()
        else:
            ans = self.browse_category(category, category_sort)

        return ans

    # }}}

    # Book Lists {{{
    def browse_list(self, query=None, offset=0, sort=None):
        raise NotImplementedError()
    # }}}

    # Search {{{
    def browse_search(self, query=None, offset=0, sort=None):
        raise NotImplementedError()
    # }}}

    # Book {{{
    def browse_book(self, uuid=None):
        raise NotImplementedError()
    # }}}


