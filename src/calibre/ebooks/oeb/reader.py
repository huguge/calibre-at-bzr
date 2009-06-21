"""
Container-/OPF-based input OEBBook reader.
"""
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import sys, os, uuid, copy, re
from itertools import izip
from urlparse import urldefrag, urlparse
from urllib import unquote as urlunquote
from mimetypes import guess_type
from collections import defaultdict

from lxml import etree
import cssutils

from calibre.ebooks.oeb.base import OPF1_NS, OPF2_NS, OPF2_NSMAP, DC11_NS, \
    DC_NSES, OPF
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES, OEB_IMAGES, \
    PAGE_MAP_MIME, JPEG_MIME, NCX_MIME, SVG_MIME
from calibre.ebooks.oeb.base import XMLDECL_RE, COLLAPSE_RE, \
    ENTITY_RE, MS_COVER_TYPE, iterlinks
from calibre.ebooks.oeb.base import namespace, barename, qname, XPath, xpath, \
                                    urlnormalize, BINARY_MIME, \
                                    OEBError, OEBBook, DirContainer
from calibre.ebooks.oeb.writer import OEBWriter
from calibre.ebooks.oeb.entitydefs import ENTITYDEFS
from calibre.ebooks.metadata.epub import CoverRenderer
from calibre.startup import get_lang
from calibre.ptempfile import TemporaryDirectory

__all__ = ['OEBReader']

class OEBReader(object):
    """Read an OEBPS 1.x or OPF/OPS 2.0 file collection."""

    COVER_SVG_XP    = XPath('h:body//svg:svg[position() = 1]')
    COVER_OBJECT_XP = XPath('h:body//h:object[@data][position() = 1]')

    Container = DirContainer
    """Container type used to access book files.  Override in sub-classes."""

    DEFAULT_PROFILE = 'PRS505'
    """Default renderer profile for content read with this Reader."""

    TRANSFORMS = []
    """List of transforms to apply to content read with this Reader."""

    @classmethod
    def config(cls, cfg):
        """Add any book-reading options to the :class:`Config` object
        :param:`cfg`.
        """
        return

    @classmethod
    def generate(cls, opts):
        """Generate a Reader instance from command-line options."""
        return cls()

    def __call__(self, oeb, path):
        """Read the book at :param:`path` into the :class:`OEBBook` object
        :param:`oeb`.
        """
        self.oeb = oeb
        self.logger = self.log = oeb.logger
        oeb.container = self.Container(path, self.logger)
        oeb.container.log = oeb.log
        opf = self._read_opf()
        self._all_from_opf(opf)
        return oeb

    def _clean_opf(self, opf):
        nsmap = {}
        for elem in opf.iter(tag=etree.Element):
            nsmap.update(elem.nsmap)
        for elem in opf.iter(tag=etree.Element):
            if namespace(elem.tag) in ('', OPF1_NS):
                elem.tag = OPF(barename(elem.tag))
        nsmap.update(OPF2_NSMAP)
        attrib = dict(opf.attrib)
        nroot = etree.Element(OPF('package'),
            nsmap={None: OPF2_NS}, attrib=attrib)
        metadata = etree.SubElement(nroot, OPF('metadata'), nsmap=nsmap)
        ignored = (OPF('dc-metadata'), OPF('x-metadata'))
        for elem in xpath(opf, 'o2:metadata//*'):
            if elem.tag in ignored:
                continue
            if namespace(elem.tag) in DC_NSES:
                tag = barename(elem.tag).lower()
                elem.tag = '{%s}%s' % (DC11_NS, tag)
            metadata.append(elem)
        for element in xpath(opf, 'o2:metadata//o2:meta'):
            metadata.append(element)
        for tag in ('o2:manifest', 'o2:spine', 'o2:tours', 'o2:guide'):
            for element in xpath(opf, tag):
                nroot.append(element)
        return nroot

    def _read_opf(self):
        data = self.oeb.container.read(None)
        data = self.oeb.decode(data)
        data = XMLDECL_RE.sub('', data)
        try:
            opf = etree.fromstring(data)
        except etree.XMLSyntaxError:
            repl = lambda m: ENTITYDEFS.get(m.group(1), m.group(0))
            data = ENTITY_RE.sub(repl, data)
            try:
                opf = etree.fromstring(data)
                self.logger.warn('OPF contains invalid HTML named entities')
            except etree.XMLSyntaxError:
                data = re.sub(r'(?is)<tours>.+</tours>', '', data)
                self.logger.warn('OPF contains invalid tours section')
                opf = etree.fromstring(data)

        ns = namespace(opf.tag)
        if ns not in ('', OPF1_NS, OPF2_NS):
            raise OEBError('Invalid namespace %r for OPF document' % ns)
        opf = self._clean_opf(opf)
        return opf

    def _metadata_from_opf(self, opf):
        uid = opf.get('unique-identifier', None)
        self.oeb.uid = None
        metadata = self.oeb.metadata
        for elem in xpath(opf, '/o2:package/o2:metadata//*'):
            term = elem.tag
            value = elem.text
            attrib = dict(elem.attrib)
            nsmap = elem.nsmap
            if term == OPF('meta'):
                term = qname(attrib.pop('name', None), nsmap)
                value = attrib.pop('content', None)
            if value:
                value = COLLAPSE_RE.sub(' ', value.strip())
            if term and (value or attrib):
                metadata.add(term, value, attrib, nsmap=nsmap)
        haveuuid = haveid = False
        for ident in metadata.identifier:
            if unicode(ident).startswith('urn:uuid:'):
                haveuuid = True
            if 'id' in ident.attrib:
                haveid = True
        if not (haveuuid and haveid):
            bookid = "urn:uuid:%s" % str(uuid.uuid4())
            metadata.add('identifier', bookid, id='calibre-uuid')
        if uid is None:
            self.logger.warn(u'Unique-identifier not specified')
        for item in metadata.identifier:
            if not item.id:
                continue
            if uid is None or item.id == uid:
                self.oeb.uid = item
                break
        else:
            self.logger.warn(u'Unique-identifier %r not found' % uid)
            for ident in metadata.identifier:
                if 'id' in ident.attrib:
                    self.oeb.uid = metadata.identifier[0]
                    break
        if not metadata.language:
            self.logger.warn(u'Language not specified')
            metadata.add('language', get_lang())
        if not metadata.creator:
            self.logger.warn('Creator not specified')
            metadata.add('creator', self.oeb.translate(__('Unknown')))
        if not metadata.title:
            self.logger.warn('Title not specified')
            metadata.add('title', self.oeb.translate(__('Unknown')))

    def _manifest_prune_invalid(self):
        '''
        Remove items from manifest that contain invalid data. This prevents
        catastrophic conversion failure, when a few files contain corrupted
        data.
        '''
        bad = []
        check = OEB_DOCS.union(OEB_STYLES)
        for item in list(self.oeb.manifest.values()):
            if item.media_type in check:
                try:
                    item.data
                except:
                    self.logger.exception('Failed to parse content in %s'%
                            item.href)
                    bad.append(item)
                    self.oeb.manifest.remove(item)
        return bad

    def _manifest_add_missing(self, invalid):
        manifest = self.oeb.manifest
        known = set(manifest.hrefs)
        unchecked = set(manifest.values())
        bad = []
        while unchecked:
            new = set()
            for item in unchecked:
                if (item.media_type in OEB_DOCS or
                    item.media_type[-4:] in ('/xml', '+xml')) and \
                   item.data is not None:
                    hrefs = [r[2] for r in iterlinks(item.data)]
                    for href in hrefs:
                        href, _ = urldefrag(href)
                        if not href:
                            continue
                        href = item.abshref(urlnormalize(href))
                        scheme = urlparse(href).scheme
                        if not scheme and href not in known:
                            new.add(href)
                elif item.media_type in OEB_STYLES:
                    for url in cssutils.getUrls(item.data):
                        href, _ = urldefrag(url)
                        href = item.abshref(urlnormalize(href))
                        scheme = urlparse(href).scheme
                        if not scheme and href not in known:
                            new.add(href)
            unchecked.clear()
            for href in new:
                known.add(href)
                is_invalid = False
                for item in invalid:
                    if href == item.abshref(urlnormalize(href)):
                        is_invalid = True
                        break
                if is_invalid:
                    continue
                if not self.oeb.container.exists(href):
                    self.logger.warn('Referenced file %r not found' % href)
                    continue
                self.logger.warn('Referenced file %r not in manifest' % href)
                id, _ = manifest.generate(id='added')
                guessed = guess_type(href)[0]
                media_type = guessed or BINARY_MIME
                added = manifest.add(id, href, media_type)
                unchecked.add(added)

    def _manifest_from_opf(self, opf):
        manifest = self.oeb.manifest
        for elem in xpath(opf, '/o2:package/o2:manifest/o2:item'):
            id = elem.get('id')
            href = elem.get('href')
            media_type = elem.get('media-type', None)
            if media_type is None:
                media_type = elem.get('mediatype', None)
            if media_type is None or media_type == 'text/xml':
                guessed = guess_type(href)[0]
                media_type = guessed or media_type or BINARY_MIME
            if hasattr(media_type, 'lower'):
                media_type = media_type.lower()
            fallback = elem.get('fallback')
            if href in manifest.hrefs:
                self.logger.warn(u'Duplicate manifest entry for %r' % href)
                continue
            if not self.oeb.container.exists(href):
                self.logger.warn(u'Manifest item %r not found' % href)
                continue
            if id in manifest.ids:
                self.logger.warn(u'Duplicate manifest id %r' % id)
                id, href = manifest.generate(id, href)
            manifest.add(id, href, media_type, fallback)
        invalid = self._manifest_prune_invalid()
        self._manifest_add_missing(invalid)

    def _spine_add_extra(self):
        manifest = self.oeb.manifest
        spine = self.oeb.spine
        unchecked = set(spine)
        selector = XPath('h:body//h:a/@href')
        extras = set()
        while unchecked:
            new = set()
            for item in unchecked:
                if item.media_type not in OEB_DOCS:
                    # TODO: handle fallback chains
                    continue
                for href in selector(item.data):
                    href, _ = urldefrag(href)
                    if not href:
                        continue
                    href = item.abshref(urlnormalize(href))
                    if href not in manifest.hrefs:
                        continue
                    found = manifest.hrefs[href]
                    if found.media_type not in OEB_DOCS or \
                       found in spine or found in extras:
                        continue
                    new.add(found)
            extras.update(new)
            unchecked = new
        version = int(self.oeb.version[0])
        for item in sorted(extras):
            if version >= 2:
                self.logger.warn(
                    'Spine-referenced file %r not in spine' % item.href)
            spine.add(item, linear=False)

    def _spine_from_opf(self, opf):
        spine = self.oeb.spine
        manifest = self.oeb.manifest
        for elem in xpath(opf, '/o2:package/o2:spine/o2:itemref'):
            idref = elem.get('idref')
            if idref not in manifest.ids:
                self.logger.warn(u'Spine item %r not found' % idref)
                continue
            item = manifest.ids[idref]
            spine.add(item, elem.get('linear'))
        if len(spine) == 0:
            raise OEBError("Spine is empty")
        self._spine_add_extra()

    def _guide_from_opf(self, opf):
        guide = self.oeb.guide
        manifest = self.oeb.manifest
        for elem in xpath(opf, '/o2:package/o2:guide/o2:reference'):
            href = elem.get('href')
            path = urldefrag(href)[0]
            if path not in manifest.hrefs:
                self.logger.warn(u'Guide reference %r not found' % href)
                continue
            guide.add(elem.get('type'), elem.get('title'), href)

    def _find_ncx(self, opf):
        result = xpath(opf, '/o2:package/o2:spine/@toc')
        if result:
            id = result[0]
            if id not in self.oeb.manifest.ids:
                return None
            item = self.oeb.manifest.ids[id]
            self.oeb.manifest.remove(item)
            return item
        for item in self.oeb.manifest.values():
            if item.media_type == NCX_MIME:
                self.oeb.manifest.remove(item)
                return item
        return None

    def _toc_from_navpoint(self, item, toc, navpoint):
        children = xpath(navpoint, 'ncx:navPoint')
        for child in children:
            title = ''.join(xpath(child, 'ncx:navLabel/ncx:text/text()'))
            title = COLLAPSE_RE.sub(' ', title.strip())
            href = xpath(child, 'ncx:content/@src')
            if not title or not href:
                continue
            href = item.abshref(urlnormalize(href[0]))
            path, _ = urldefrag(href)
            if path not in self.oeb.manifest.hrefs:
                self.logger.warn('TOC reference %r not found' % href)
                continue
            id = child.get('id')
            klass = child.get('class', 'chapter')

            po = int(child.get('playOrder', self.oeb.toc.next_play_order()))

            authorElement = xpath(child,
                    'descendant::mbp:meta[@name = "author"]')
            if authorElement :
                author = authorElement[0].text
            else :
                author = None

            descriptionElement = xpath(child,
                    'descendant::mbp:meta[@name = "description"]')
            if descriptionElement :
                description = descriptionElement[0].text
            else :
                description = None

            node = toc.add(title, href, id=id, klass=klass,
                    play_order=po, description=description, author=author)

            self._toc_from_navpoint(item, node, child)

    def _toc_from_ncx(self, item):
        if item is None:
            return False
        self.log.debug('Reading TOC from NCX...')
        ncx = item.data
        title = ''.join(xpath(ncx, 'ncx:docTitle/ncx:text/text()'))
        title = COLLAPSE_RE.sub(' ', title.strip())
        title = title or unicode(self.oeb.metadata.title[0])
        toc = self.oeb.toc
        toc.title = title
        navmaps = xpath(ncx, 'ncx:navMap')
        for navmap in navmaps:
            self._toc_from_navpoint(item, toc, navmap)
        return True

    def _toc_from_tour(self, opf):
        result = xpath(opf, 'o2:tours/o2:tour')
        if not result:
            return False
        self.log.debug('Reading TOC from tour...')
        tour = result[0]
        toc = self.oeb.toc
        toc.title = tour.get('title')
        sites = xpath(tour, 'o2:site')
        for site in sites:
            title = site.get('title')
            href = site.get('href')
            if not title or not href:
                continue
            path, _ = urldefrag(urlnormalize(href))
            if path not in self.oeb.manifest.hrefs:
                self.logger.warn('TOC reference %r not found' % href)
                continue
            id = site.get('id')
            toc.add(title, href, id=id)
        return True

    def _toc_from_html(self, opf):
        if 'toc' not in self.oeb.guide:
            return False
        self.log.debug('Reading TOC from HTML...')
        itempath, frag = urldefrag(self.oeb.guide['toc'].href)
        item = self.oeb.manifest.hrefs[itempath]
        html = item.data
        if frag:
            elems = xpath(html, './/*[@id="%s"]' % frag)
            if not elems:
                elems = xpath(html, './/*[@name="%s"]' % frag)
            elem = elems[0] if elems else html
            while elem != html and not xpath(elem, './/h:a[@href]'):
                elem = elem.getparent()
            html = elem
        titles = defaultdict(list)
        order = []
        for anchor in xpath(html, './/h:a[@href]'):
            href = anchor.attrib['href']
            href = item.abshref(urlnormalize(href))
            path, frag = urldefrag(href)
            if path not in self.oeb.manifest.hrefs:
                continue
            title = ' '.join(xpath(anchor, './/text()'))
            title = COLLAPSE_RE.sub(' ', title.strip())
            if href not in titles:
                order.append(href)
            titles[href].append(title)
        toc = self.oeb.toc
        for href in order:
            toc.add(' '.join(titles[href]), href)
        return True

    def _toc_from_spine(self, opf):
        self.log.warn('Generating default TOC from spine...')
        toc = self.oeb.toc
        titles = []
        headers = []
        for item in self.oeb.spine:
            if not item.linear: continue
            html = item.data
            title = ''.join(xpath(html, '/h:html/h:head/h:title/text()'))
            title = COLLAPSE_RE.sub(' ', title.strip())
            if title:
                titles.append(title)
            headers.append('(unlabled)')
            for tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'strong'):
                expr = '/h:html/h:body//h:%s[position()=1]/text()'
                header = ''.join(xpath(html, expr % tag))
                header = COLLAPSE_RE.sub(' ', header.strip())
                if header:
                    headers[-1] = header
                    break
        use = titles
        if len(titles) > len(set(titles)):
            use = headers
        for title, item in izip(use, self.oeb.spine):
            if not item.linear: continue
            toc.add(title, item.href)
        return True

    def _toc_from_opf(self, opf, item):
        self.oeb.auto_generated_toc = False
        if self._toc_from_ncx(item): return
        # Prefer HTML to tour based TOC, since several LIT files
        # have good HTML TOCs but bad tour based TOCs
        if self._toc_from_html(opf): return
        if self._toc_from_tour(opf): return
        self._toc_from_spine(opf)
        self.oeb.auto_generated_toc = True

    def _pages_from_ncx(self, opf, item):
        if item is None:
            return False
        ncx = item.data
        ptargets = xpath(ncx, 'ncx:pageList/ncx:pageTarget')
        if not ptargets:
            return False
        pages = self.oeb.pages
        for ptarget in ptargets:
            name = ''.join(xpath(ptarget, 'ncx:navLabel/ncx:text/text()'))
            name = COLLAPSE_RE.sub(' ', name.strip())
            href = xpath(ptarget, 'ncx:content/@src')
            if not href:
                continue
            href = item.abshref(urlnormalize(href[0]))
            id = ptarget.get('id')
            type = ptarget.get('type', 'normal')
            klass = ptarget.get('class')
            pages.add(name, href, type=type, id=id, klass=klass)
        return True

    def _find_page_map(self, opf):
        result = xpath(opf, '/o2:package/o2:spine/@page-map')
        if result:
            id = result[0]
            if id not in self.oeb.manifest.ids:
                return None
            item = self.oeb.manifest.ids[id]
            self.oeb.manifest.remove(item)
            return item
        for item in self.oeb.manifest.values():
            if item.media_type == PAGE_MAP_MIME:
                self.oeb.manifest.remove(item)
                return item
        return None

    def _pages_from_page_map(self, opf):
        item = self._find_page_map(opf)
        if item is None:
            return False
        pmap = item.data
        pages = self.oeb.pages
        for page in xpath(pmap, 'o2:page'):
            name = page.get('name', '')
            href = page.get('href')
            if not href:
                continue
            name = COLLAPSE_RE.sub(' ', name.strip())
            href = item.abshref(urlnormalize(href))
            type = 'normal'
            if not name:
                type = 'special'
            elif name.lower().strip('ivxlcdm') == '':
                type = 'front'
            pages.add(name, href, type=type)
        return True

    def _pages_from_opf(self, opf, item):
        if self._pages_from_ncx(opf, item): return
        if self._pages_from_page_map(opf): return
        return

    def _cover_from_html(self, hcover):
        with TemporaryDirectory('_html_cover') as tdir:
            writer = OEBWriter()
            writer(self.oeb, tdir)
            path = os.path.join(tdir, urlunquote(hcover.href))
            renderer = CoverRenderer(path)
            data = renderer.image_data
        id, href = self.oeb.manifest.generate('cover', 'cover.jpeg')
        item = self.oeb.manifest.add(id, href, JPEG_MIME, data=data)
        return item

    def _locate_cover_image(self):
        if self.oeb.metadata.cover:
            id = unicode(self.oeb.metadata.cover[0])
            item = self.oeb.manifest.ids.get(id, None)
            if item is not None and item.media_type in OEB_IMAGES:
                return item
            else:
                self.logger.warn('Invalid cover image @id %r' % id)
        hcover = self.oeb.spine[0]
        if 'cover' in self.oeb.guide:
            href = self.oeb.guide['cover'].href
            item = self.oeb.manifest.hrefs[href]
            media_type = item.media_type
            if media_type in OEB_IMAGES:
                return item
            elif media_type in OEB_DOCS:
                hcover = item
        html = hcover.data
        if MS_COVER_TYPE in self.oeb.guide:
            href = self.oeb.guide[MS_COVER_TYPE].href
            item = self.oeb.manifest.hrefs.get(href, None)
            if item is not None and item.media_type in OEB_IMAGES:
                return item
        if self.COVER_SVG_XP(html):
            svg = copy.deepcopy(self.COVER_SVG_XP(html)[0])
            href = os.path.splitext(hcover.href)[0] + '.svg'
            id, href = self.oeb.manifest.generate(hcover.id, href)
            item = self.oeb.manifest.add(id, href, SVG_MIME, data=svg)
            return item
        if self.COVER_OBJECT_XP(html):
            object = self.COVER_OBJECT_XP(html)[0]
            href = hcover.abshref(object.get('data'))
            item = self.oeb.manifest.hrefs.get(href, None)
            if item is not None and item.media_type in OEB_IMAGES:
                return item
        return self._cover_from_html(hcover)

    def _ensure_cover_image(self):
        cover = self._locate_cover_image()
        if self.oeb.metadata.cover:
            self.oeb.metadata.cover[0].value = cover.id
            return
        self.oeb.metadata.add('cover', cover.id)

    def _all_from_opf(self, opf):
        self.oeb.version = opf.get('version', '1.2')
        self._metadata_from_opf(opf)
        self._manifest_from_opf(opf)
        self._spine_from_opf(opf)
        self._guide_from_opf(opf)
        item = self._find_ncx(opf)
        self._toc_from_opf(opf, item)
        self._pages_from_opf(opf, item)
        #self._ensure_cover_image()


def main(argv=sys.argv):
    reader = OEBReader()
    for arg in argv[1:]:
        oeb = reader(OEBBook(), arg)
        for name, doc in oeb.to_opf1().values():
            print etree.tostring(doc, pretty_print=True)
        for name, doc in oeb.to_opf2(page_map=True).values():
            print etree.tostring(doc, pretty_print=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
