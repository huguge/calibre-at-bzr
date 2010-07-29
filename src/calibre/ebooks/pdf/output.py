# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Convert OEB ebook format to PDF.
'''

import glob
import os

from calibre.customize.conversion import OutputFormatPlugin, \
    OptionRecommendation
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.pdf.writer import PDFWriter, ImagePDFWriter, PDFMetadata
from calibre.ebooks.pdf.pageoptions import UNITS, PAPER_SIZES, \
    ORIENTATIONS

class PDFOutput(OutputFormatPlugin):

    name = 'PDF Output'
    author = 'John Schember and Kovid Goyal'
    file_type = 'pdf'

    options = set([
                    OptionRecommendation(name='unit', recommended_value='inch',
                        level=OptionRecommendation.LOW, short_switch='u', choices=UNITS.keys(),
                        help=_('The unit of measure. Default is inch. Choices '
                        'are %s '
                        'Note: This does not override the unit for margins!') % UNITS.keys()),
                    OptionRecommendation(name='paper_size', recommended_value='letter',
                        level=OptionRecommendation.LOW, choices=PAPER_SIZES.keys(),
                        help=_('The size of the paper. This size will be overridden when an '
                        'output profile is used. Default is letter. Choices '
                        'are %s') % PAPER_SIZES.keys()),
                    OptionRecommendation(name='custom_size', recommended_value=None,
                        help=_('Custom size of the document. Use the form widthxheight '
                        'EG. `123x321` to specify the width and height. '
                        'This overrides any specified paper-size.')),
                    OptionRecommendation(name='orientation', recommended_value='portrait',
                        level=OptionRecommendation.LOW, choices=ORIENTATIONS.keys(),
                        help=_('The orientation of the page. Default is portrait. Choices '
                        'are %s') % ORIENTATIONS.keys()),
                    OptionRecommendation(name='preserve_cover_aspect_ratio',
                        recommended_value=False,
                        help=_('Preserve the aspect ratio of the cover, instead'
                            ' of stretching it to fill the ull first page of the'
                            ' generated pdf.')
                        ),
                 ])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        self.oeb = oeb_book
        self.input_plugin, self.opts, self.log = input_plugin, opts, log
        self.output_path = output_path
        self.metadata = oeb_book.metadata
        self.cover_data = None

        # Remove page-break-before on <body> element as it causes
        # blank pages in PDF Output
        from calibre.ebooks.oeb.base import OEB_STYLES
        stylesheet = None
        for item in self.oeb.manifest:
            if item.media_type.lower() in OEB_STYLES:
                stylesheet = item
                break
        if stylesheet is not None:
            from cssutils.css import CSSRule
            for rule in stylesheet.data.cssRules.rulesOfType(CSSRule.STYLE_RULE):
                if rule.selectorList.selectorText == '.calibre':
                    rule.style.removeProperty('page-break-before')
                    rule.style.removeProperty('page-break-after')


        if input_plugin.is_image_collection:
            log.debug('Converting input as an image collection...')
            self.convert_images(input_plugin.get_images())
        else:
            log.debug('Converting input as a text based book...')
            self.convert_text(oeb_book)

    def convert_images(self, images):
        self.write(ImagePDFWriter, images)

    def get_cover_data(self):
        g, m = self.oeb.guide, self.oeb.manifest
        if 'titlepage' not in g:
            if 'cover' in g:
                href = g['cover'].href
                from calibre.ebooks.oeb.base import urlnormalize
                for item in m:
                    if item.href == urlnormalize(href):
                        self.cover_data = item.data

    def convert_text(self, oeb_book):
        self.log.debug('Serializing oeb input to disk for processing...')
        self.get_cover_data()

        with TemporaryDirectory('_pdf_out') as oeb_dir:
            from calibre.customize.ui import plugin_for_output_format
            oeb_output = plugin_for_output_format('oeb')
            oeb_output.convert(oeb_book, oeb_dir, self.input_plugin, self.opts, self.log)

            opfpath = glob.glob(os.path.join(oeb_dir, '*.opf'))[0]
            opf = OPF(opfpath, os.path.dirname(opfpath))

            self.write(PDFWriter, [s.path for s in opf.spine])

    def write(self, Writer, items):
        writer = Writer(self.opts, self.log, cover_data=self.cover_data)

        close = False
        if not hasattr(self.output_path, 'write'):
            close = True
            if not os.path.exists(os.path.dirname(self.output_path)) and os.path.dirname(self.output_path) != '':
                os.makedirs(os.path.dirname(self.output_path))
            out_stream = open(self.output_path, 'wb')
        else:
            out_stream = self.output_path

        out_stream.seek(0)
        out_stream.truncate()
        self.log.debug('Rendering pages to PDF...')
        writer.dump(items, out_stream, PDFMetadata(self.metadata))

        if close:
            out_stream.close()

