# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Read meta information from TXT files
'''


import os
import glob
import re

from calibre.ebooks.metadata import MetaInformation
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.zipfile import ZipFile

def get_metadata(stream, extract_cover=True):
    """ Return metadata as a L{MetaInfo} object """
    mi = MetaInformation(_('Unknown'), [_('Unknown')])
    stream.seek(0)

    pml = ''
    if stream.name.endswith('.pmlz'):
        with TemporaryDirectory('_unpmlz') as tdir:
            zf = ZipFile(stream)
            zf.extractall(tdir)

            pmls = glob.glob(os.path.join(tdir, '*.pml'))
            for p in pmls:
                with open(p, 'r+b') as p_stream:
                    pml += p_stream.read()
            if extract_cover:
                mi.cover_data = get_cover(os.path.splitext(os.path.basename(stream.name))[0], tdir, True)
    else:
        pml = stream.read()
        if extract_cover:
            mi.cover_data = get_cover(os.path.splitext(os.path.basename(stream.name))[0], os.path.abspath(os.path.dirname(stream.name)))

    for comment in re.findall(r'(?mus)\\v.*?\\v', pml):
        m = re.search(r'TITLE="(.*?)"', comment)
        if m:
            mi.title = m.group(1).strip().decode('cp1252', 'replace')
        m = re.search(r'AUTHOR="(.*?)"', comment)
        if m:
            if mi.authors == [_('Unknown')]:
                mi.authors = []
            mi.authors.append(m.group(1).strip().decode('cp1252', 'replace'))
        m = re.search(r'PUBLISHER="(.*?)"', comment)
        if m:
            mi.publisher = m.group(1).strip().decode('cp1252', 'replace')
        m = re.search(r'COPYRIGHT="(.*?)"', comment)
        if m:
            mi.rights = m.group(1).strip().decode('cp1252', 'replace')
        m = re.search(r'ISBN="(.*?)"', comment)
        if m:
            mi.isbn = m.group(1).strip().decode('cp1252', 'replace')

    return mi

def get_cover(name, tdir, top_level=False):
    cover_path = ''
    cover_data = None

    if top_level:
        cover_path = os.path.join(tdir, 'cover.png') if os.path.exists(os.path.join(tdir, 'cover.png')) else ''
    if not cover_path:
        cover_path = os.path.join(tdir, name + '_img', 'cover.png') if os.path.exists(os.path.join(tdir, name + '_img', 'cover.png')) else os.path.join(os.path.join(tdir, 'images'), 'cover.png') if os.path.exists(os.path.join(os.path.join(tdir, 'images'), 'cover.png')) else ''
    if cover_path:
        with open(cover_path, 'r+b') as cstream:
            cover_data = cstream.read()

    return ('png', cover_data)
