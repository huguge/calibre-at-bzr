#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time
from struct import pack

from calibre.ebooks.mobi.utils import RECORD_SIZE, utf8_text
from calibre.ebooks.mobi.writer8.header import Header
from calibre.ebooks.mobi.writer2 import (PALMDOC, UNCOMPRESSED)
from calibre.ebooks.mobi.langcodes import iana2mobi
from calibre.ebooks.mobi.writer8.exth import build_exth
from calibre.utils.filenames import ascii_filename

NULL_INDEX = 0xffffffff

class MOBIHeader(Header): # {{{
    '''
    Represents the first record in a MOBI file, contains all the metadata about
    the file.
    '''

    FILE_VERSION = 8

    DEFINITION = '''
    # 0: Compression
    compression = DYN

    # 2: Unused
    unused1 = zeroes(2)

    # 4: Text length
    text_length = DYN

    # 8: Last text record
    last_text_record = DYN

    # 10: Text record size
    record_size = {record_size}

    # 12: Unused
    unused2

    # 16: Ident
    ident = b'MOBI'

    # 20: Header length
    header_length = 248

    # 24: Book Type (0x2 - Book, 0x101 - News hierarchical, 0x102 - News
    # (flat), 0x103 - News magazine same as 0x101)
    book_type = DYN

    # 28: Text encoding (utf-8 = 65001)
    encoding = 65001

    # 32: UID
    uid = random.randint(0, 0xffffffff)

    # 36: File version
    file_version = {file_version}

    # 40: Meta orth record (Chunk table index in KF8)
    meta_orth_record = DYN

    # 44: Meta infl index
    meta_infl_index = NULL

    # 48: Extra indices
    extra_index0 = NULL
    extra_index1 = NULL
    extra_index2 = NULL
    extra_index3 = NULL
    extra_index4 = NULL
    extra_index5 = NULL
    extra_index6 = NULL
    extra_index7 = NULL

    # 80: First non text record
    first_non_text_record = DYN

    # 84: Title offset
    title_offset

    # 88: Title Length
    title_length = DYN

    # 92: Language code
    language_code = DYN

    # 96: Dictionary in and out languages
    in_lang
    out_lang

    # 104: Min version
    min_version = {file_version}

    # 108: First resource record
    first_resource_record = DYN

    # 112: Huff/CDIC compression
    huff_first_record
    huff_count

    # 120: DATP records
    datp_first_record
    datp_count

    # 128: EXTH flags
    exth_flags = DYN

    # 132: Unknown
    unknown = zeroes(32)

    # 164: DRM
    drm_offset = NULL
    drm_count = NULL
    drm_size
    drm_flags

    # 180: Unknown
    unknown2 = zeroes(12)

    # 192: FDST
    fdst_record = DYN
    fdst_count = DYN

    # 200: FCI
    fcis_record = NULL
    fcis_count

    # 208: FLIS
    flis_record = NULL
    flis_count

    # 216: Unknown
    unknown3 = zeroes(8)

    # 224: SRCS
    srcs_record = NULL
    srcs_count

    # 232: Unknown
    unknown4 = nulls(8)

    # 240: Extra data flags
    # 0b1 - extra multibyte bytes after text records
    # 0b10 - TBS indexing data (only used in MOBI 6)
    # 0b100 - uncrossable breaks only used in MOBI 6
    extra_data_flags = 1

    # 244: KF8 Indices
    ncx_index = DYN
    chunk_index = DYN
    skel_index = DYN
    datp_index = NULL
    guide_index = DYN

    # 264: EXTH
    exth = DYN

    # Full title
    full_title = DYN

    # Padding to allow amazon's DTP service to add data
    padding = zeroes(8192)
    '''.format(record_size=RECORD_SIZE, file_version=FILE_VERSION)

    SHORT_FIELDS = {'compression', 'last_text_record', 'record_size'}
    ALIGN = True
    POSITIONS = {'title_offset':'full_title'}

    def format_value(self, name, val):
        if name == 'compression':
            val = PALMDOC if val else UNCOMPRESSED
        return super(MOBIHeader, self).format_value(name, val)

# }}}

# Fields that need to be set in the MOBI Header are

class KF8Book(object):

    def __init__(self, writer):
        self.build_records(writer)

    def build_records(self, writer):
        metadata = writer.oeb.metadata
        # The text records
        for x in ('last_text_record_idx', 'first_non_text_record_idx'):
            setattr(self, x.rpartition('_')[0], getattr(writer, x))
        self.records = writer.records
        self.text_length = writer.text_length

        # KF8 Indices
        self.chunk_index = self.meta_orth_record = len(self.records)
        self.records.extend(writer.chunk_records)
        self.skel_index = len(self.records)
        self.records.extend(writer.skel_records)
        self.guide_index = NULL_INDEX
        if writer.guide_records:
            self.guide_index = len(self.records)
            self.records.extend(writer.guide_records)
        self.ncx_index = NULL_INDEX
        if writer.ncx_records:
            self.ncx_index = len(self.records)
            self.records.extend(writer.ncx_records)

        # Resources
        resources = writer.resources
        for x in ('cover_offset', 'thumbnail_offset', 'masthead_offset'):
            setattr(self, x, getattr(resources, x))

        self.first_resource_record = NULL_INDEX
        if resources.records:
            self.first_resource_record = len(self.records)
            self.records.extend(resources.records)

        self.first_resource_record = len(self.records)
        self.num_of_resources = len(resources.records)

        # FDST
        self.fdst_count = writer.fdst_count
        self.fdst_record = len(self.records)
        self.records.extend(writer.fdst_records)

        # EOF
        self.records.append(b'\xe9\x8e\r\n') # EOF record


        # Miscellaneous header fields
        self.compression = writer.compress
        self.book_type = 0x101 if writer.opts.mobi_periodical else 2
        self.full_title = utf8_text(unicode(metadata.title[0]))
        self.title_length = len(self.full_title)

        self.language_code = iana2mobi(str(metadata.language[0]))
        self.exth_flags = 0b1010000
        if writer.opts.mobi_periodical:
            self.exth_flags |= 0b1000

        self.opts = writer.opts
        self.start_offset = writer.start_offset
        self.metadata = metadata

    @property
    def record0(self):
        ''' We generate the EXTH header and record0 dynamically, to allow other
        code to customize various values after build_record() has been
        called'''
        opts = self.opts
        kuc = 0 if self.num_of_resources > 0 else None
        self.exth = build_exth(self.metadata,
                prefer_author_sort=opts.prefer_author_sort,
                is_periodical=opts.mobi_periodical,
                share_not_sync=opts.share_not_sync,
                cover_offset=self.cover_offset,
                thumbnail_offset=self.thumbnail_offset,
                num_of_resources=self.num_of_resources,
                kf8_unknown_count=kuc, be_kindlegen2=True,
                start_offset=self.start_offset, mobi_doctype=self.book_type)

        kwargs = {field:getattr(self, field) for field in
                ('compression', 'text_length', 'last_text_record',
                'book_type', 'meta_orth_record', 'first_non_text_record',
                'title_length', 'language_code', 'first_resource_record',
                'exth_flags', 'fdst_record', 'fdst_count', 'ncx_index',
                'chunk_index', 'skel_index', 'guide_index', 'exth',
                'full_title')}
        return MOBIHeader()(**kwargs)

    def write(self, outpath):
        records = [self.record0] + self.records[1:]

        with open(outpath, 'wb') as f:

            # Write PalmDB Header

            title = ascii_filename(self.full_title.decode('utf-8')).replace(
                    ' ', '_')[:31]
            title += (b'\0' * (32 - len(title)))
            now = int(time.time())
            nrecords = len(records)
            f.write(title)
            f.write(pack(b'>HHIIIIII', 0, 0, now, now, 0, 0, 0, 0))
            f.write(b'BOOKMOBI')
            f.write(pack(b'>IIH', (2*nrecords)-1, 0, nrecords))
            offset = f.tell() + (8 * nrecords) + 2
            for i, record in enumerate(records):
                f.write(pack(b'>I', offset))
                f.write(b'\0' + pack(b'>I', 2*i)[1:])
                offset += len(record)
            f.write(b'\0\0')

            for rec in records:
                f.write(rec)

