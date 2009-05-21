# -*- coding: utf-8 -*-

'''
Read content from ereader pdb file.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.pdb.formatreader import FormatReader
from calibre.ebooks.pdb.ereader.reader132 import Reader132
from calibre.ebooks.pdb.ereader.reader202 import Reader202

class Reader(FormatReader):

    def __init__(self, header, stream, log, encoding=None):
        record0_size = len(header.section_data(0))

        if record0_size == 132:
            self.reader = Reader132(header, stream, log, encoding)
        elif record0_size == 202:
            self.reader = Reader202(header, stream, log, encoding)
        else:
            raise ValueError('Unknown eReader Header')

    def extract_content(self, output_dir):
        return self.reader.extract_content(output_dir)

    def dump_pml(self):
        return self.reader.dump_pml()

    def dump_images(self):
        return self.reader.dump_images()
