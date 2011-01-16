# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.ebooks.conversion.preprocess import DocAnalysis, Dehyphenator
from calibre.ebooks.chardet import detect
from calibre.ebooks.txt.processor import convert_basic, convert_markdown, \
    separate_paragraphs_single_line, separate_paragraphs_print_formatted, \
    preserve_spaces, detect_paragraph_type, detect_formatting_type, \
    normalize_line_endings, convert_textile
from calibre import _ent_pat, xml_entity_to_unicode

class TXTInput(InputFormatPlugin):

    name        = 'TXT Input'
    author      = 'John Schember'
    description = 'Convert TXT files to HTML'
    file_types  = set(['txt'])

    options = set([
        OptionRecommendation(name='paragraph_type', recommended_value='auto',
            choices=['auto', 'block', 'single', 'print', 'unformatted'],
            help=_('Paragraph structure.\n'
                   'choices are [\'auto\', \'block\', \'single\', \'print\', \'unformatted\']\n'
                   '* auto: Try to auto detect paragraph type.\n'
                   '* block: Treat a blank line as a paragraph break.\n'
                   '* single: Assume every line is a paragraph.\n'
                   '* print:  Assume every line starting with 2+ spaces or a tab '
                   'starts a paragraph.'
                   '* unformatted: Most lines have hard line breaks, few/no blank lines or indents.')),
        OptionRecommendation(name='formatting_type', recommended_value='auto',
            choices=['auto', 'none', 'heuristic', 'markdown'],
            help=_('Formatting used within the document.'
                   '* auto: Automatically decide which formatting processor to use.\n'
                   '* none: Do not process the document formatting. Everything is a '
                   'paragraph and no styling is applied.\n'
                   '* heuristic: Process using heuristics to determine formatting such '
                   'as chapter headings and italic text.\n'
                   '* textile: Processing using textile formatting.\n'
                   '* markdown: Processing using markdown formatting. '
                   'To learn more about markdown see')+' http://daringfireball.net/projects/markdown/'),
        OptionRecommendation(name='preserve_spaces', recommended_value=False,
            help=_('Normally extra spaces are condensed into a single space. '
                'With this option all spaces will be displayed.')),
        OptionRecommendation(name="markdown_disable_toc", recommended_value=False,
            help=_('Do not insert a Table of Contents into the output text.')),
    ])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        log.debug('Reading text from file...')

        txt = stream.read()
        # Get the encoding of the document.
        if options.input_encoding:
            ienc = options.input_encoding
            log.debug('Using user specified input encoding of %s' % ienc)
        else:
            det_encoding = detect(txt)
            ienc = det_encoding['encoding']
            log.debug('Detected input encoding as %s with a confidence of %s%%' % (ienc, det_encoding['confidence'] * 100))
        if not ienc:
            ienc = 'utf-8'
            log.debug('No input encoding specified and could not auto detect using %s' % ienc)
        txt = txt.decode(ienc, 'replace')

        txt = _ent_pat.sub(xml_entity_to_unicode, txt)
        # Preserve spaces will replace multiple spaces to a space
        # followed by the &nbsp; entity.
        if options.preserve_spaces:
            txt = preserve_spaces(txt)

        # Normalize line endings
        txt = normalize_line_endings(txt)

        # Get length for hyphen removal and punctuation unwrap
        docanalysis = DocAnalysis('txt', txt)
        length = docanalysis.line_length(.5)

        if options.formatting_type == 'auto':
            options.formatting_type = detect_formatting_type(txt)

        if options.formatting_type == 'markdown':
            log.debug('Running text though markdown conversion...')
            try:
                html = convert_markdown(txt, disable_toc=options.markdown_disable_toc)
            except RuntimeError:
                raise ValueError('This txt file has malformed markup, it cannot be'
                    ' converted by calibre. See http://daringfireball.net/projects/markdown/syntax')
        elif options.formatting_type == 'textile':
            log.debug('Running text though textile conversion...')
            html = convert_textile(txt)
        else:
            # Determine the paragraph type of the document.
            if options.paragraph_type == 'auto':
                options.paragraph_type = detect_paragraph_type(txt)
                if options.paragraph_type == 'unknown':
                    log.debug('Could not reliably determine paragraph type using block')
                    options.paragraph_type = 'block'
                else:
                    log.debug('Auto detected paragraph type as %s' % options.paragraph_type)

            # Dehyphenate
            dehyphenator = Dehyphenator(options.verbose, log=getattr(self, 'log', None))
            txt = dehyphenator(txt,'txt', length)

            # We don't check for block because the processor assumes block.
            # single and print at transformed to block for processing.

            if options.paragraph_type == 'single' or options.paragraph_type == 'unformatted':
                txt = separate_paragraphs_single_line(txt)
            elif options.paragraph_type == 'print':
                txt = separate_paragraphs_print_formatted(txt)

            if options.paragraph_type == 'unformatted':
                from calibre.ebooks.conversion.utils import PreProcessor
                # get length

                # unwrap lines based on punctuation
                preprocessor = PreProcessor(options, log=getattr(self, 'log', None))
                txt = preprocessor.punctuation_unwrap(length, txt, 'txt')

            flow_size = getattr(options, 'flow_size', 0)
            html = convert_basic(txt, epub_split_size_kb=flow_size)

            if options.formatting_type == 'heuristic':
                setattr(options, 'enable_heuristics', True)
                setattr(options, 'markup_chapter_headings', True)
                setattr(options, 'italicize_common_cases', True)
                setattr(options, 'fix_indents', True)
                setattr(options, 'delete_blank_paragraphs', True)
                setattr(options, 'format_scene_breaks', True)
                setattr(options, 'dehyphenate', True)

        from calibre.customize.ui import plugin_for_input_format
        html_input = plugin_for_input_format('html')
        for opt in html_input.options:
            setattr(options, opt.option.name, opt.recommended_value)
        options.input_encoding = 'utf-8'
        base = os.getcwdu()
        if hasattr(stream, 'name'):
            base = os.path.dirname(stream.name)
        fname = os.path.join(base, 'index.html')
        c = 0
        while os.path.exists(fname):
            c += 1
            fname = 'index%d.html'%c
        htmlfile = open(fname, 'wb')
        with htmlfile:
            htmlfile.write(html.encode('utf-8'))
        odi = options.debug_pipeline
        options.debug_pipeline = None
        oeb = html_input.convert(open(htmlfile.name, 'rb'), options, 'html', log,
                {})
        options.debug_pipeline = odi
        os.remove(htmlfile.name)
        return oeb
