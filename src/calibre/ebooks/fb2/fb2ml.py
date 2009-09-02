# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into FB2 markup
'''

import os
import cStringIO
from base64 import b64encode

try:
    from PIL import Image
    Image
except ImportError:
    import Image

from lxml import etree

from calibre import prepare_string_for_xml
from calibre.constants import __appname__, __version__
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES

TAG_MAP = {
    'b' : 'strong',
    'i' : 'emphasis',
    'p' : 'p',
    'li' : 'p',
}

TAG_SPACE = [
    'div',
    'br',
]

TAG_IMAGES = [
    'img',
]

TAG_LINKS = [
    'a',
]

STYLES = [
    ('font-weight', {'bold'   : 'strong', 'bolder' : 'strong'}),
    ('font-style', {'italic' : 'emphasis'}),
]

class FB2MLizer(object):
    
    def __init__(self, log):
        self.log = log
        self.image_hrefs = {}
        self.link_hrefs = {}
        
    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to FB2 markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        return self.fb2mlize_spine()
        
    def fb2mlize_spine(self):
        self.image_hrefs = {}
        self.link_hrefs = {}
        output = [self.fb2_header()]
        output.append(self.get_cover_page())
        output.append(u'ghji87yhjko0Caliblre-toc-placeholder-for-insertion-later8ujko0987yjk')
        output.append(self.get_text())
        output.append(self.fb2_body_footer())
        output.append(self.fb2mlize_images())
        output.append(self.fb2_footer())
        output = ''.join(output).replace(u'ghji87yhjko0Caliblre-toc-placeholder-for-insertion-later8ujko0987yjk', self.get_toc())
        return u'<?xml version="1.0" encoding="UTF-8"?>\n%s' % etree.tostring(etree.fromstring(output), encoding=unicode, pretty_print=True)

    def fb2_header(self):
        author_first = u''
        author_middle = u''
        author_last = u''
        author_parts = self.oeb_book.metadata.creator[0].value.split(' ')
        
        if len(author_parts) == 1:
            author_last = author_parts[0]
        elif len(author_parts) == 2:
            author_first = author_parts[0]
            author_last = author_parts[1]
        else:
            author_first = author_parts[0]
            author_middle = ' '.join(author_parts[1:-2])
            author_last = author_parts[-1]

        return u'<FictionBook xmlns:xlink="http://www.w3.org/1999/xlink" ' \
        'xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">\n' \
        '<description>\n<title-info>\n ' \
        '<author>\n<first-name>%s</first-name>\n<middle-name>%s' \
        '</middle-name>\n<last-name>%s</last-name>\n</author>\n' \
        '<book-title>%s</book-title> ' \
        '</title-info><document-info> ' \
        '<program-used>%s - %s</program-used></document-info>\n' \
        '</description>\n<body>\n<section>' % (author_first, author_middle,
            author_last, self.oeb_book.metadata.title[0].value,
            __appname__, __version__)

    def get_cover_page(self):
        output = u''
        if 'titlepage' in self.oeb_book.guide:
            self.log.debug('Generating cover page...')
            href = self.oeb_book.guide['titlepage'].href
            item = self.oeb_book.manifest.hrefs[href]
            if item.spine_position is None:
                stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts.output_profile)
                output += self.dump_text(item.data.find(XHTML('body')), stylizer, item)
        return output

    def get_toc(self):
        toc = [u'']
        if self.opts.inline_toc:
            self.log.debug('Generating table of contents...')
            toc.append(u'<p>%s</p>' % _('Table of Contents:'))
            for item in self.oeb_book.toc:
                if item.href in self.link_hrefs.keys():
                    toc.append('<p><a xlink:href="#%s">%s</a></p>\n' % (self.link_hrefs[item.href], item.title))
                else:
                    self.oeb.warn('Ignoring toc item: %s not found in document.' % item)
        return ''.join(toc)

    def get_text(self):
        text = [u'']
        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to FictionBook2 XML' % item.href)
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts.output_profile)
            text.append(self.add_page_anchor(item))
            text += self.dump_text(item.data.find(XHTML('body')), stylizer, item)
        return ''.join(text)

    def fb2_body_footer(self):
        return u'\n</section>\n</body>'
        
    def fb2_footer(self):
        return u'</FictionBook>'

    def add_page_anchor(self, page):
        return self.get_anchor(page, '')

    def get_anchor(self, page, aid):
        aid = prepare_string_for_xml(aid)
        aid = '%s#%s' % (page.href, aid)
        if aid not in self.link_hrefs.keys():
            self.link_hrefs[aid] = 'calibre_link-%s' % len(self.link_hrefs.keys())
        aid = self.link_hrefs[aid]
        return '<v id="%s"></v>' % aid

    def fb2mlize_images(self):
        images = [u'']
        for item in self.oeb_book.manifest:
            if item.media_type in OEB_RASTER_IMAGES:
                try:
                    im = Image.open(cStringIO.StringIO(item.data)).convert('RGB')
                    data = cStringIO.StringIO()
                    im.save(data, 'JPEG')
                    data = data.getvalue()

                    raw_data = b64encode(data)
                    # Don't put the encoded image on a single line.
                    data = ''
                    col = 1
                    for char in raw_data:
                        if col == 72:
                            data += '\n'
                            col = 1
                        col += 1
                        data += char
                    images.append('<binary id="%s" content-type="%s">%s\n</binary>' % (self.image_hrefs.get(item.href, '0000.JPEG'), item.media_type, data))
                except Exception as e:
                    self.log.error('Error: Could not include file %s becuase ' \
                        '%s.' % (item.href, e))
        return ''.join(images)

    def dump_text(self, elem, stylizer, page, tag_stack=[]):
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return [u'']
            
        fb2_text = [u'']
        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return [u'']
        
        tag = barename(elem.tag)
        tag_count = 0

        if tag in TAG_IMAGES:
            if elem.attrib.get('src', None):
                if page.abshref(elem.attrib['src']) not in self.image_hrefs.keys():
                    self.image_hrefs[page.abshref(elem.attrib['src'])] = '%s.jpg' % len(self.image_hrefs.keys())
                fb2_text.append('<image xlink:href="#%s" />' % self.image_hrefs[page.abshref(elem.attrib['src'])])

        if tag in TAG_LINKS:
            href = elem.get('href')
            if href:
                href = prepare_string_for_xml(page.abshref(href))
                if '://' in href:
                    fb2_text.append('<a xlink:href="%s">' % href)
                else:
                    if '#' not in href:
                        href += '#'
                    if href not in self.link_hrefs.keys():
                        self.link_hrefs[href] = 'calibre_link-%s' % len(self.link_hrefs.keys())
                    href = self.link_hrefs[href]
                    fb2_text.append('<a xlink:href="#%s">' % href)
                tag_count += 1
                tag_stack.append('a')

        # Anchor ids
        id_name = elem.get('id')
        if id_name:
            fb2_text.append(self.get_anchor(page, id_name))

        fb2_tag = TAG_MAP.get(tag, None)
        if fb2_tag and fb2_tag not in tag_stack:
            tag_count += 1
            fb2_text.append('<%s>' % fb2_tag)
            tag_stack.append(fb2_tag)

        # Processes style information
        for s in STYLES:
            style_tag = s[1].get(style[s[0]], None)
            if style_tag:
                tag_count += 1
                fb2_text.append('<%s>' % style_tag)
                tag_stack.append(style_tag)

        if tag in TAG_SPACE:
            if not fb2_text or fb2_text[-1] != ' ':
                fb2_text.append(' ')

        if hasattr(elem, 'text') and elem.text != None:
            fb2_text.append(prepare_string_for_xml(elem.text))
        
        for item in elem:
            fb2_text += self.dump_text(item, stylizer, page, tag_stack)

        close_tag_list = []
        for i in range(0, tag_count):
            close_tag_list.insert(0, tag_stack.pop())
        fb2_text += self.close_tags(close_tag_list)

        if hasattr(elem, 'tail') and elem.tail != None:
            if 'p' not in tag_stack:
                fb2_text.append('<p>%s</p>' % prepare_string_for_xml(elem.tail))
            else:
                fb2_text.append(prepare_string_for_xml(elem.tail))

        return fb2_text

    def close_tags(self, tags):
        fb2_text = [u'']
        for i in range(0, len(tags)):
            fb2_tag = tags.pop()
            fb2_text.append('</%s>' % fb2_tag)

        return fb2_text
