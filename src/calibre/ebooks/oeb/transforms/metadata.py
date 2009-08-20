#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from datetime import datetime

def meta_info_to_oeb_metadata(mi, m, log):
    from calibre.ebooks.oeb.base import OPF
    if mi.title:
        m.clear('title')
        m.add('title', mi.title)
    if mi.title_sort:
        if not m.title:
            m.add('title', mi.title_sort)
        m.title[0].file_as = mi.title_sort
    if mi.authors:
        m.filter('creator', lambda x : x.role.lower() in ['aut', ''])
        for a in mi.authors:
            attrib = {'role':'aut'}
            if mi.author_sort:
                attrib[OPF('file-as')] = mi.author_sort
            m.add('creator', a, attrib=attrib)
    if mi.book_producer:
        m.filter('contributor', lambda x : x.role.lower() == 'bkp')
        m.add('contributor', mi.book_producer, role='bkp')
    if mi.comments:
        m.clear('description')
        m.add('description', mi.comments)
    if mi.publisher:
        m.clear('publisher')
        m.add('publisher', mi.publisher)
    if mi.series:
        m.clear('series')
        m.add('series', mi.series)
    if mi.isbn:
        has = False
        for x in m.identifier:
            if x.scheme.lower() == 'isbn':
                x.content = mi.isbn
                has = True
        if not has:
            m.add('identifier', mi.isbn, scheme='ISBN')
    if mi.language:
        m.clear('language')
        m.add('language', mi.language)
    if mi.series_index is not None:
        m.clear('series_index')
        m.add('series_index', mi.format_series_index())
    if mi.rating is not None:
        m.clear('rating')
        m.add('rating', '%.2f'%mi.rating)
    if mi.tags:
        m.clear('subject')
        for t in mi.tags:
            m.add('subject', t)
    if mi.pubdate is not None:
        m.clear('date')
        m.add('date', mi.pubdate.isoformat())
    if mi.timestamp is not None:
        m.clear('timestamp')
        m.add('timestamp', mi.timestamp.isoformat())
    if mi.rights is not None:
        m.clear('rights')
        m.add('rights', mi.rights)
    if mi.publication_type is not None:
        m.clear('publication_type')
        m.add('publication_type', mi.publication_type)
    if not m.timestamp:
        m.add('timestamp', datetime.now().isoformat())


class MergeMetadata(object):
    'Merge in user metadata, including cover'

    def __call__(self, oeb, mi, opts):
        self.oeb, self.log = oeb, oeb.log
        m = self.oeb.metadata
        meta_info_to_oeb_metadata(mi, m, oeb.log)
        self.log('Merging user specified metadata...')
        cover_id = self.set_cover(mi, opts.prefer_metadata_cover)
        m.clear('cover')
        if cover_id is not None:
            m.add('cover', cover_id)


    def set_cover(self, mi, prefer_metadata_cover):
        cdata = ''
        if mi.cover and os.access(mi.cover, os.R_OK):
            cdata = open(mi.cover, 'rb').read()
        elif mi.cover_data and mi.cover_data[-1]:
            cdata = mi.cover_data[1]
        id = old_cover = None
        if 'cover' in self.oeb.guide:
            old_cover = self.oeb.guide['cover']
        if prefer_metadata_cover and old_cover is not None:
            cdata = ''
        if cdata:
            self.oeb.guide.remove('cover')
            self.oeb.guide.remove('titlepage')
        if old_cover is not None:
            if old_cover.href in self.oeb.manifest.hrefs:
                item = self.oeb.manifest.hrefs[old_cover.href]
                if not cdata:
                    return item.id
                self.oeb.manifest.remove(item)
            elif not cdata:
                id = self.oeb.manifest.generate(id='cover')
                self.oeb.manifest.add(id, old_cover.href, 'image/jpeg')
                return id
        if cdata:
            id, href = self.oeb.manifest.generate('cover', 'cover.jpg')
            self.oeb.manifest.add(id, href, 'image/jpeg', data=cdata)
            self.oeb.guide.add('cover', 'Cover', href)
        return id

