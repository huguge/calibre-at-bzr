#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


class Clean(object):
    '''Clean up guide, leaving only a pointer to the cover'''

    def __call__(self, oeb, opts):
        from calibre.ebooks.oeb.base import urldefrag
        self.oeb, self.log, self.opts = oeb, oeb.log, opts

        protected_hrefs = set([])
        if 'titlepage' in self.oeb.guide:
            protected_hrefs.add(urldefrag(
                self.oeb.guide['titlepage'].href)[0])
        if 'cover' not in self.oeb.guide:
            covers = []
            for x in ('other.ms-coverimage-standard',
                    'other.ms-titleimage-standard', 'other.ms-titleimage',
                    'other.ms-coverimage', 'other.ms-thumbimage-standard',
                    'other.ms-thumbimage'):
                if x in self.oeb.guide:
                    href = self.oeb.guide[x].href
                    item = self.oeb.manifest.hrefs[href]
                    covers.append([self.oeb.guide[x], len(item.data)])
            covers.sort(cmp=lambda x,y:cmp(x[1], y[1]), reverse=True)
            if covers:
                ref = covers[0][0]
                if len(covers) > 1:
                    self.log('Choosing %s:%s as the cover'%(ref.type, ref.href))
                ref.type = 'cover'
                self.oeb.guide.refs['cover'] = ref
                protected_hrefs.add(urldefrag(ref.href)[0])
        else:
            protected_hrefs.add(urldefrag(self.oeb.guide.refs['cover'].href)[0])

        for x in list(self.oeb.guide):
            href = urldefrag(self.oeb.guide[x].href)[0]
            if x.lower() != ('cover', 'titlepage'):
                try:
                    if href not in protected_hrefs:
                        self.oeb.manifest.remove(self.oeb.manifest.hrefs[href])
                except KeyError:
                    pass
                self.oeb.guide.remove(x)


