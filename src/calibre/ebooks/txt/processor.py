# -*- coding: utf-8 -*-

'''
Read content from txt file.
'''

import os, re

from calibre import prepare_string_for_xml
from calibre.ebooks.markdown import markdown
from calibre.ebooks.metadata.opf2 import OPFCreator

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

HTML_TEMPLATE = u'<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/><title>%s</title></head><body>\n%s\n</body></html>'

def convert_basic(txt, title='', epub_split_size_kb=0):
    # Strip whitespace from the beginning and end of the line. Also replace
    # all line breaks with \n.
    txt = '\n'.join([line.strip() for line in txt.splitlines()])

    # Condense redundant spaces
    txt = re.sub('[ ]{2,}', ' ', txt)

    # Remove blank lines from the beginning and end of the document.
    txt = re.sub('^\s+(?=.)', '', txt)
    txt = re.sub('(?<=.)\s+$', '', txt)
    # Remove excessive line breaks.
    txt = re.sub('\n{3,}', '\n\n', txt)
    #remove ASCII invalid chars : 0 to 8 and 11-14 to 24
    illegal_char = re.compile('\x00|\x01|\x02|\x03|\x04|\x05|\x06|\x07|\x08| \
        \x0B|\x0E|\x0F|\x10|\x11|\x12|\x13|\x14|\x15|\x16|\x17|\x18')
    txt = illegal_char.sub('', txt)
    
    #Takes care if there is no point to split
    if epub_split_size_kb > 0:
        length_byte = len(txt)
        #Calculating the average chunk value for easy splitting as EPUB (+2 as a safe margin)
        chunk_size = long(length_byte / (int(length_byte / (epub_split_size_kb * 1024) ) + 2 ))
        #if there are chunks with a superior size then go and break
        if (len(filter(lambda x: len(x) > chunk_size, txt.split('\n\n')))) :
            txt = '\n\n'.join([split_string_separator(line, chunk_size) 
                for line in txt.split('\n\n')])

    lines = []
    # Split into paragraphs based on having a blank line between text.
    for line in txt.split('\n\n'):
        if line.strip():
            lines.append(u'<p>%s</p>' % prepare_string_for_xml(line.replace('\n', ' ')))

    return HTML_TEMPLATE % (title, u'\n'.join(lines))

def convert_markdown(txt, title='', disable_toc=False):
    md = markdown.Markdown(
          extensions=['footnotes', 'tables', 'toc'],
          extension_configs={"toc": {"disable_toc": disable_toc}},
          safe_mode=False)
    return HTML_TEMPLATE % (title, md.convert(txt))

def separate_paragraphs_single_line(txt):
    txt = txt.replace('\r\n', '\n')
    txt = txt.replace('\r', '\n')
    txt = re.sub(u'(?<=.)\n(?=.)', '\n\n', txt)
    return txt

def separate_paragraphs_print_formatted(txt):
    txt = re.sub(u'(?miu)^(\t+|[ ]{2,})(?=.)', '\n\t', txt)
    return txt

def preserve_spaces(txt):
    txt = txt.replace(' ', '&nbsp;')
    txt = txt.replace('\t', '&#09;')
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

