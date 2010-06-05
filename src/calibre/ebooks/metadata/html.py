#!/usr/bin/env  python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Try to read metadata from an HTML file.
'''

import re

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.chardet import xml_to_unicode
from calibre import entity_to_unicode

def get_metadata(stream):
    src = stream.read()
    return get_metadata_(src)

def get_metadata_(src, encoding=None):
    if not isinstance(src, unicode):
        if not encoding:
            src = xml_to_unicode(src)[0]
        else:
            src = src.decode(encoding, 'replace')

    # Title
    title = None
    pat = re.compile(r'<!--.*?TITLE=(?P<q>[\'"])(.+?)(?P=q).*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        title = match.group(2)
    else:
        pat = re.compile('<title>([^<>]+?)</title>', re.IGNORECASE)
        match = pat.search(src)
        if match:
            title = match.group(1)

    # Author
    author = None
    pat = re.compile(r'<!--.*?AUTHOR=(?P<q>[\'"])(.+?)(?P=q).*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        author = match.group(2).replace(',', ';')

    ent_pat = re.compile(r'&(\S+)?;')
    title = ent_pat.sub(entity_to_unicode, title)
    if author:
        author = ent_pat.sub(entity_to_unicode, author)
    mi = MetaInformation(title, [author] if author else None)

    # Publisher
    pat = re.compile(r'<!--.*?PUBLISHER=(?P<q>[\'"])(.+?)(?P=q).*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        mi.publisher = match.group(2)

    # ISBN
    pat = re.compile(r'<!--.*?ISBN=[\'"]([^"\']+)[\'"].*?-->', re.DOTALL)
    match = pat.search(src)
    if match:
        isbn = match.group(1)
        mi.isbn = re.sub(r'[^0-9xX]', '', isbn)

    return mi


