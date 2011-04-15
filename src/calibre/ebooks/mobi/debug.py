#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct, datetime
from calibre.utils.date import utc_tz
from calibre.ebooks.mobi.langcodes import main_language, sub_language

class PalmDOCAttributes(object):

    class Attr(object):

        def __init__(self, name, field, val):
            self.name = name
            self.val = val & field

        def __str__(self):
            return '%s: %s'%(self.name, bool(self.val))

    def __init__(self, raw):
        self.val = struct.unpack(b'<H', raw)[0]
        self.attributes = []
        for name, field in [('Read Only', 0x02), ('Dirty AppInfoArea', 0x04),
                ('Backup this database', 0x08),
                ('Okay to install newer over existing copy, if present on PalmPilot', 0x10),
                ('Force the PalmPilot to reset after this database is installed', 0x12),
                ('Don\'t allow copy of file to be beamed to other Pilot',
                    0x14)]:
            self.attributes.append(PalmDOCAttributes.Attr(name, field,
                self.val))

    def __str__(self):
        attrs = '\n\t'.join([str(x) for x in self.attributes])
        return 'PalmDOC Attributes: %s\n\t%s'%(bin(self.val), attrs)

class PalmDB(object):

    def __init__(self, raw):
        self.raw = raw

        if self.raw.startswith(b'TPZ'):
            raise ValueError('This is a Topaz file')

        self.name     = self.raw[:32].replace(b'\x00', b'')
        self.attributes = PalmDOCAttributes(self.raw[32:34])
        self.version = struct.unpack(b'>H', self.raw[34:36])[0]

        palm_epoch = datetime.datetime(1904, 1, 1, tzinfo=utc_tz)
        self.creation_date_raw = struct.unpack(b'>I', self.raw[36:40])[0]
        self.creation_date = (palm_epoch +
                datetime.timedelta(seconds=self.creation_date_raw))
        self.modification_date_raw = struct.unpack(b'>I', self.raw[40:44])[0]
        self.modification_date = (palm_epoch +
                datetime.timedelta(seconds=self.modification_date_raw))
        self.last_backup_date_raw = struct.unpack(b'>I', self.raw[44:48])[0]
        self.last_backup_date = (palm_epoch +
                datetime.timedelta(seconds=self.last_backup_date_raw))
        self.modification_number = struct.unpack(b'>I', self.raw[48:52])[0]
        self.app_info_id = self.raw[52:56]
        self.sort_info_id = self.raw[56:60]
        self.type = self.raw[60:64]
        self.creator = self.raw[64:68]
        self.ident = self.type + self.creator
        if self.ident not in (b'BOOKMOBI', b'TEXTREAD'):
            raise ValueError('Unknown book ident: %r'%self.ident)
        self.uid_seed = self.raw[68:72]
        self.next_rec_list_id = self.raw[72:76]

        self.number_of_records, = struct.unpack(b'>H', self.raw[76:78])

    def __str__(self):
        ans = ['*'*20 + ' PalmDB Header '+ '*'*20]
        ans.append('Name: %r'%self.name)
        ans.append(str(self.attributes))
        ans.append('Version: %s'%self.version)
        ans.append('Creation date: %s (%s)'%(self.creation_date.isoformat(),
            self.creation_date_raw))
        ans.append('Modification date: %s (%s)'%(self.modification_date.isoformat(),
            self.modification_date_raw))
        ans.append('Backup date: %s (%s)'%(self.last_backup_date.isoformat(),
            self.last_backup_date_raw))
        ans.append('Modification number: %s'%self.modification_number)
        ans.append('App Info ID: %r'%self.app_info_id)
        ans.append('Sort Info ID: %r'%self.sort_info_id)
        ans.append('Type: %r'%self.type)
        ans.append('Creator: %r'%self.creator)
        ans.append('UID seed: %r'%self.uid_seed)
        ans.append('Next record list id: %r'%self.next_rec_list_id)
        ans.append('Number of records: %s'%self.number_of_records)

        return '\n'.join(ans)

class Record(object):

    def __init__(self, raw, header):
        self.offset, self.flags, self.uid = header
        self.raw = raw

    @property
    def header(self):
        return 'Offset: %d Flags: %d UID: %d'%(self.offset, self.flags,
                self.uid)

class EXTHRecord(object):

    def __init__(self, type_, data):
        self.type = type_
        self.data = data
        self.name = {
                1 : 'DRM Server id',
                2 : 'DRM Commerce id',
                3 : 'DRM ebookbase book id',
                100 : 'author',
                101 : 'publisher',
                102 : 'imprint',
                103 : 'description',
                104 : 'isbn',
                105 : 'subject',
                106 : 'publishingdate',
                107 : 'review',
                108 : 'contributor',
                109 : 'rights',
                110 : 'subjectcode',
                111 : 'type',
                112 : 'source',
                113 : 'asin',
                114 : 'versionnumber',
                115 : 'sample',
                116 : 'startreading',
                117 : 'adult',
                118 : 'retailprice',
                119 : 'retailpricecurrency',
                201 : 'coveroffset',
                202 : 'thumboffset',
                203 : 'hasfakecover',
                204 : 'Creator Software',
                205 : 'Creator Major Version', # '>I'
                206 : 'Creator Minor Version', # '>I'
                207 : 'Creator Build number', # '>I'
                208 : 'watermark',
                209 : 'tamper_proof_keys',
                300 : 'fontsignature',
                301 : 'clippinglimit', # percentage '>B'
                402 : 'publisherlimit',
                404 : 'TTS flag', # '>B' 1 - TTS disabled 0 - TTS enabled
                501 : 'cdetype', # 4 chars (PDOC or EBOK)
                502 : 'lastupdatetime',
                503 : 'updatedtitle',
        }.get(self.type, repr(self.type))

    def __str__(self):
        return '%s (%d): %r'%(self.name, self.type, self.data)

class EXTHHeader(object):

    def __init__(self, raw):
        self.raw = raw
        if not self.raw.startswith(b'EXTH'):
            raise ValueError('EXTH header does not start with EXTH')
        self.length, = struct.unpack(b'>I', self.raw[4:8])
        self.count,  = struct.unpack(b'>I', self.raw[8:12])

        pos = 12
        self.records = []
        for i in xrange(self.count):
            pos = self.read_record(pos)

    def read_record(self, pos):
        type_, length = struct.unpack(b'>II', self.raw[pos:pos+8])
        data = self.raw[(pos+8):(pos+length)]
        self.records.append(EXTHRecord(type_, data))
        return pos + length

    def __str__(self):
        ans = ['*'*20 + ' EXTH Header '+ '*'*20]
        ans.append('EXTH header length: %d'%self.length)
        ans.append('Number of EXTH records: %d'%self.count)
        ans.append('EXTH records...')
        for r in self.records:
            ans.append(str(r))
        return '\n'.join(ans)


class MOBIHeader(object):

    def __init__(self, record0):
        self.raw = record0.raw

        self.compression_raw = self.raw[:2]
        self.compression = {1: 'No compression', 2: 'PalmDoc compression',
                17480: 'HUFF/CDIC compression'}.get(struct.unpack(b'>H',
                    self.compression_raw)[0],
                    repr(self.compression_raw))
        self.unused = self.raw[2:4]
        self.text_length, = struct.unpack(b'>I', self.raw[4:8])
        self.number_of_text_records, self.text_record_size = \
                struct.unpack(b'>HH', self.raw[8:12])
        self.encryption_type_raw, = struct.unpack(b'>H', self.raw[12:14])
        self.encryption_type = {0: 'No encryption',
                1: 'Old mobipocket encryption',
                2:'Mobipocket encryption'}.get(self.encryption_type_raw,
                repr(self.encryption_type_raw))
        self.unknown = self.raw[14:16]

        self.identifier = self.raw[16:20]
        if self.identifier != b'MOBI':
            raise ValueError('Identifier %r unknown'%self.identifier)

        self.length, = struct.unpack(b'>I', self.raw[20:24])
        self.type_raw, = struct.unpack(b'>I', self.raw[24:28])
        self.type = {
                2 : 'Mobipocket book',
                3 : 'PalmDOC book',
                4 : 'Audio',
                257 : 'News',
                258 : 'News Feed',
                259 : 'News magazine',
                513 : 'PICS',
                514 : 'Word',
                515 : 'XLS',
                516 : 'PPT',
                517 : 'TEXT',
                518 : 'HTML',
            }.get(self.type_raw, repr(self.type_raw))

        self.encoding_raw, = struct.unpack(b'>I', self.raw[28:32])
        self.encoding = {
                1252 : 'cp1252',
                65001: 'utf-8',
            }.get(self.encoding_raw, repr(self.encoding_raw))
        self.uid = self.raw[32:36]
        self.file_version = struct.unpack(b'>I', self.raw[36:40])
        self.reserved = self.raw[40:80]
        self.first_non_book_record, = struct.unpack(b'>I', self.raw[80:84])
        self.fullname_offset, = struct.unpack(b'>I', self.raw[84:88])
        self.fullname_length, = struct.unpack(b'>I', self.raw[88:92])
        self.locale_raw, = struct.unpack(b'>I', self.raw[92:96])
        langcode = self.locale_raw
        langid    = langcode & 0xFF
        sublangid = (langcode >> 10) & 0xFF
        self.language = main_language.get(langid, 'ENGLISH')
        self.sublanguage = sub_language.get(sublangid, 'NEUTRAL')

        self.input_language = self.raw[96:100]
        self.output_langauage = self.raw[100:104]
        self.min_version, = struct.unpack(b'>I', self.raw[104:108])
        self.first_image_index, = struct.unpack(b'>I', self.raw[108:112])
        self.huffman_record_offset, = struct.unpack(b'>I', self.raw[112:116])
        self.huffman_record_count, = struct.unpack(b'>I', self.raw[116:120])
        self.unknown2 = self.raw[120:128]
        self.exth_flags, = struct.unpack(b'>I', self.raw[128:132])
        self.has_exth = bool(self.exth_flags & 0x40)
        self.has_drm_data = self.length >= 184 and len(self.raw) >= 184
        if self.has_drm_data:
            self.unknown3 = self.raw[132:164]
            self.drm_offset, = struct.unpack(b'>I', self.raw[164:168])
            self.drm_count, = struct.unpack(b'>I', self.raw[168:172])
            self.drm_size, = struct.unpack(b'>I', self.raw[172:176])
            self.drm_flags = bin(struct.unpack(b'>I', self.raw[176:180])[0])
        self.has_extra_data_flags = self.length >= 244 and len(self.raw) >= 244
        if self.has_extra_data_flags:
            self.unknown4 = self.raw[180:242]
            self.extra_data_flags = bin(struct.unpack(b'>H',
                self.raw[242:244])[0])

        if self.has_exth:
            self.exth_offset = 16 + self.length

            self.exth = EXTHHeader(self.raw[self.exth_offset:])

            self.end_of_exth = self.exth_offset + self.exth.length
            self.bytes_after_exth = self.fullname_offset - self.end_of_exth

    def __str__(self):
        ans = ['*'*20 + ' MOBI Header '+ '*'*20]
        ans.append('Compression: %s'%self.compression)
        ans.append('Unused: %r'%self.unused)
        ans.append('Number of text records: %d'%self.number_of_text_records)
        ans.append('Text record size: %d'%self.text_record_size)
        ans.append('Encryption: %s'%self.encryption_type)
        ans.append('Unknown: %r'%self.unknown)
        ans.append('Identifier: %r'%self.identifier)
        ans.append('Header length: %d'% self.length)
        ans.append('Type: %s'%self.type)
        ans.append('Encoding: %s'%self.encoding)
        ans.append('UID: %r'%self.uid)
        ans.append('File version: %d'%self.file_version)
        ans.append('Reserved: %r'%self.reserved)
        ans.append('First non-book record: %d'% self.first_non_book_record)
        ans.append('Full name offset: %d'%self.fullname_offset)
        ans.append('Full name length: %d bytes'%self.fullname_length)
        ans.append('Langcode: %r'%self.locale_raw)
        ans.append('Language: %s'%self.language)
        ans.append('Sub language: %s'%self.sublanguage)
        ans.append('Input language: %r'%self.input_language)
        ans.append('Output language: %r'%self.output_langauage)
        ans.append('Min version: %d'%self.min_version)
        ans.append('First Image index: %d'%self.first_image_index)
        ans.append('Huffman record offset: %d'%self.huffman_record_offset)
        ans.append('Huffman record count: %d'%self.huffman_record_count)
        ans.append('Unknown2: %r'%self.unknown2)
        ans.append('EXTH flags: %r (%s)'%(self.exth_flags, self.has_exth))
        if self.has_drm_data:
            ans.append('Unknown3: %r'%self.unknown3)
            ans.append('DRM Offset: %s'%self.drm_offset)
            ans.append('DRM Count: %s'%self.drm_count)
            ans.append('DRM Size: %s'%self.drm_size)
            ans.append('DRM Flags: %r'%self.drm_flags)
        if self.has_extra_data_flags:
            ans.append('Unknown4: %r'%self.unknown4)
            ans.append('Extra data flags: %r'%self.extra_data_flags)

        ans = '\n'.join(ans)

        if self.has_exth:
            ans += '\n\n' + str(self.exth)
            ans += '\n\nBytes after EXTH: %d'%self.bytes_after_exth

        ans += '\nNumber of bytes after full name: %d' % (len(self.raw) - (self.fullname_offset +
                self.fullname_length))

        ans += '\nRecord 0 length: %d'%len(self.raw)
        return ans

class MOBIFile(object):

    def __init__(self, stream):
        self.raw = stream.read()

        self.palmdb = PalmDB(self.raw[:78])

        self.record_headers = []
        self.records = []
        for i in xrange(self.palmdb.number_of_records):
            pos = 78 + i * 8
            offset, a1, a2, a3, a4 = struct.unpack(b'>LBBBB', self.raw[pos:pos+8])
            flags, val = a1, a2 << 16 | a3 << 8 | a4
            self.record_headers.append((offset, flags, val))

        def section(section_number):
            if section_number == self.palmdb.number_of_records - 1:
                end_off = len(self.raw)
            else:
                end_off = self.record_headers[section_number + 1][0]
            off = self.record_headers[section_number][0]
            return self.raw[off:end_off]

        for i in range(self.palmdb.number_of_records):
            self.records.append(Record(section(i), self.record_headers[i]))

        self.mobi_header = MOBIHeader(self.records[0])


    def print_header(self):
        print (str(self.palmdb).encode('utf-8'))
        print ()
        print ('Record headers:')
        for i, r in enumerate(self.records):
            print ('%6d. %s'%(i, r.header))

        print ()
        print (str(self.mobi_header).encode('utf-8'))

def inspect_mobi(path_or_stream):
    stream = (path_or_stream if hasattr(path_or_stream, 'read') else
            open(path_or_stream, 'rb'))
    f = MOBIFile(stream)
    f.print_header()

if __name__ == '__main__':
    import sys
    f = MOBIFile(open(sys.argv[1], 'rb'))
    f.print_header()

