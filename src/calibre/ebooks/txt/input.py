# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.txt.processor import convert_basic, convert_markdown, \
    separate_paragraphs_single_line, separate_paragraphs_print_formatted, \
    preserve_spaces
from calibre import _ent_pat, xml_entity_to_unicode

class TXTInput(InputFormatPlugin):

    name        = 'TXT Input'
    author      = 'John Schember'
    description = 'Convert TXT files to HTML'
    file_types  = set(['txt'])

    options = set([
        OptionRecommendation(name='single_line_paras', recommended_value=False,
            help=_('Normally calibre treats blank lines as paragraph markers. '
                'With this option it will assume that every line represents '
                'a paragraph instead.')),
        OptionRecommendation(name='print_formatted_paras', recommended_value=False,
            help=_('Normally calibre treats blank lines as paragraph markers. '
                'With this option it will assume that every line starting with '
                'an indent (either a tab or 2+ spaces) represents a paragraph. '
                'Paragraphs end when the next line that starts with an indent '
                'is reached.')),
        OptionRecommendation(name='preserve_spaces', recommended_value=False,
            help=_('Normally extra spaces are condensed into a single space. '
                'With this option all spaces will be displayed.')),
        OptionRecommendation(name='markdown', recommended_value=False,
            help=_('Run the text input through the markdown pre-processor. To '
                'learn more about markdown see')+' http://daringfireball.net/projects/markdown/'),
        OptionRecommendation(name="markdown_disable_toc", recommended_value=False,
            help=_('Do not insert a Table of Contents into the output text.')),
    ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        ienc = stream.encoding if stream.encoding else 'utf-8'
        if options.input_encoding:
            ienc = options.input_encoding
        log.debug('Reading text from file...')
        txt = stream.read().decode(ienc, 'replace')

        # Adjust paragraph formatting as requested
        if options.single_line_paras:
            txt = separate_paragraphs_single_line(txt)
        if options.print_formatted_paras:
            txt = separate_paragraphs_print_formatted(txt)
        if options.preserve_spaces:
            txt = preserve_spaces(txt)

        txt = _ent_pat.sub(xml_entity_to_unicode, txt)
        txt = txt.encode('utf-8')

        if options.markdown:
            log.debug('Running text though markdown conversion...')
            try:
                html = convert_markdown(txt, disable_toc=options.markdown_disable_toc)
            except RuntimeError:
                raise ValueError('This txt file has malformed markup, it cannot be'
                    ' converted by calibre. See http://daringfireball.net/projects/markdown/syntax')
        else:
            flow_size = getattr(options, 'flow_size', 0)
            html = convert_basic(txt, epub_split_size_kb=flow_size)

        from calibre.customize.ui import plugin_for_input_format
        html_input = plugin_for_input_format('html')
        for opt in html_input.options:
            setattr(options, opt.option.name, opt.recommended_value)
        options.input_encoding = 'utf-8'
        base = os.getcwdu()
        if hasattr(stream, 'name'):
            base = os.path.dirname(stream.name)
        htmlfile = open(os.path.join(base, 'temp_calibre_txt_input_to_html.html'),
                'wb')
        htmlfile.write(html) #html.encode('utf-8')
        htmlfile.close()
        cwd = os.getcwdu()
        odi = options.debug_pipeline
        options.debug_pipeline = None
        oeb = html_input(open(htmlfile.name, 'rb'), options, 'html', log,
                {}, cwd)
        options.debug_pipeline = odi
        os.remove(htmlfile.name)
        return oeb
