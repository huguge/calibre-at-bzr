# -*- coding: utf-8 -*-
__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


'''
Read content from txt file.
'''

import os, re

from calibre import prepare_string_for_xml, isbytestring
from calibre.ebooks.metadata.opf2 import OPFCreator
from calibre.ebooks.conversion.preprocess import DocAnalysis
from calibre.utils.cleantext import clean_ascii_chars

HTML_TEMPLATE = u'<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/><title>%s</title></head><body>\n%s\n</body></html>'

def clean_txt(txt):
    if isbytestring(txt):
        txt = txt.decode('utf-8', 'replace')
    # Strip whitespace from the end of the line. Also replace
    # all line breaks with \n.
    txt = '\n'.join([line.rstrip() for line in txt.splitlines()])
    
    # Replace whitespace at the beginning of the list with &nbsp;
    txt = re.sub('(?m)(?P<space>[ ]+)', lambda mo: '&nbsp;' * mo.groups('space').count(' '), txt)
    txt = re.sub('(?m)(?P<space>[\t]+)', lambda mo: '&nbsp;' * 4 * mo.groups('space').count('\t'), txt)

    # Condense redundant spaces
    txt = re.sub('[ ]{2,}', ' ', txt)

    # Remove blank lines from the beginning and end of the document.
    txt = re.sub('^\s+(?=.)', '', txt)
    txt = re.sub('(?<=.)\s+$', '', txt)
    # Remove excessive line breaks.
    txt = re.sub('\n{5,}', '\n\n\n\n', txt)
    #remove ASCII invalid chars : 0 to 8 and 11-14 to 24
    txt = clean_ascii_chars(txt)

    return txt

def split_txt(txt, epub_split_size_kb=0):
    #Takes care if there is no point to split
    if epub_split_size_kb > 0:
        if isinstance(txt, unicode):
            txt = txt.encode('utf-8')
        length_byte = len(txt)
        #Calculating the average chunk value for easy splitting as EPUB (+2 as a safe margin)
        chunk_size = long(length_byte / (int(length_byte / (epub_split_size_kb * 1024) ) + 2 ))
        #if there are chunks with a superior size then go and break
        if (len(filter(lambda x: len(x) > chunk_size, txt.split('\n\n')))) :
            txt = '\n\n'.join([split_string_separator(line, chunk_size)
                for line in txt.split('\n\n')])
    if isbytestring(txt):
        txt = txt.decode('utf-8')

    return txt

def convert_basic(txt, title='', epub_split_size_kb=0):
    txt = clean_txt(txt)
    txt = split_txt(txt, epub_split_size_kb)

    lines = []
    blank_count = 0
    # Split into paragraphs based on having a blank line between text.
    for line in txt.split('\n'):
        if line.strip():
            blank_count = 0
            lines.append(u'<p>%s</p>' % prepare_string_for_xml(line.replace('\n', ' ')))
        else:
            blank_count += 1
            if blank_count == 2:
                lines.append(u'<p>&nbsp;</p>')

    return HTML_TEMPLATE % (title, u'\n'.join(lines))

def convert_markdown(txt, title='', disable_toc=False):
    from calibre.ebooks.markdown import markdown
    md = markdown.Markdown(
          extensions=['footnotes', 'tables', 'toc'],
          extension_configs={"toc": {"disable_toc": disable_toc}},
          safe_mode=False)
    return HTML_TEMPLATE % (title, md.convert(txt))

def convert_textile(txt, title=''):
    from calibre.ebooks.textile import textile
    html = textile(txt, encoding='utf-8')
    return HTML_TEMPLATE % (title, html)

def normalize_line_endings(txt):
    txt = txt.replace('\r\n', '\n')
    txt = txt.replace('\r', '\n')
    return txt

def separate_paragraphs_single_line(txt):
    txt = txt.replace('\n', '\n\n')
    return txt

def separate_paragraphs_print_formatted(txt):
    txt = re.sub(u'(?miu)^(\t+|[ ]{2,})(?=.)', '\n\t', txt)
    return txt

def preserve_spaces(txt):
    txt = re.sub('(?P<space>[ ]{2,})', lambda mo: ' ' + ('&nbsp;' * (len(mo.group('space')) - 1)), txt)
    txt = txt.replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')
    return txt

def opf_writer(path, opf_name, manifest, spine, mi):
    opf = OPFCreator(path, mi)
    opf.create_manifest(manifest)
    opf.create_spine(spine)
    with open(os.path.join(path, opf_name), 'wb') as opffile:
        opf.render(opffile)

def split_string_separator(txt, size) :
    if len(txt) > size:
        txt = ''.join([re.sub(u'\.(?P<ends>[^.]*)$', '.\n\n\g<ends>',
            txt[i:i+size], 1) for i in
            xrange(0, len(txt), size)])
    return txt

def detect_paragraph_type(txt):
    '''
    Tries to determine the formatting of the document.

    block: Paragraphs are separated by a blank line.
    single: Each line is a paragraph.
    print: Each paragraph starts with a 2+ spaces or a tab
           and ends when a new paragraph is reached.
    unformatted: most lines have hard line breaks, few/no blank lines or indents

    returns block, single, print, unformatted
    '''
    txt = txt.replace('\r\n', '\n')
    txt = txt.replace('\r', '\n')
    txt_line_count = len(re.findall('(?mu)^\s*.+$', txt))

    # Check for hard line breaks - true if 55% of the doc breaks in the same region
    docanalysis = DocAnalysis('txt', txt)
    hardbreaks = docanalysis.line_histogram(.55)

    if hardbreaks:
        # Determine print percentage
        tab_line_count = len(re.findall('(?mu)^(\t|\s{2,}).+$', txt))
        print_percent = tab_line_count / float(txt_line_count)

        # Determine block percentage
        empty_line_count = len(re.findall('(?mu)^\s*$', txt))
        block_percent = empty_line_count / float(txt_line_count)

        # Compare the two types - the type with the larger number of instances wins
        # in cases where only one or the other represents the vast majority of the document neither wins
        if print_percent >= block_percent:
            if .15 <= print_percent <= .75:
                return 'print'
        elif .15 <= block_percent <= .75:
            return 'block'

        # Assume unformatted text with hardbreaks if nothing else matches
        return 'unformatted'

    # return single if hardbreaks is false
    return 'single'


def detect_formatting_type(txt):
    markdown_count = 0
    textile_count = 0

    # Check for markdown
    # Headings
    markdown_count += len(re.findall('(?mu)^#+', txt))
    markdown_count += len(re.findall('(?mu)^=+$', txt))
    markdown_count += len(re.findall('(?mu)^-+$', txt))
    # Images
    markdown_count += len(re.findall('(?u)!\[.*?\]\(.+?\)', txt))
    # Links
    markdown_count += len(re.findall('(?u)(^|(?P<pre>[^!]))\[.*?\]\([^)]+\)', txt))

    # Check for textile
    # Headings
    textile_count += len(re.findall(r'(?mu)^h[1-6]\.', txt))
    # Block quote.
    textile_count += len(re.findall(r'(?mu)^bq\.', txt))
    # Images
    textile_count += len(re.findall(r'\![^\s]+(?=.*?/)(:[^\s]+)*', txt))
    # Links
    textile_count += len(re.findall(r'"(?=".*?\()(\(.+?\))*[^\(]+?(\(.+?\))*":[^\s]+', txt))

    if markdown_count > 5 or textile_count > 5:
        if markdown_count > textile_count:
            return 'markdown'
        else:
            return 'textile'

    return 'heuristic'
