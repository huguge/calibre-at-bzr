##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''Read meta information from epub files'''

from __future__ import with_statement

import sys, os

from zipfile import ZipFile, BadZipfile
from cStringIO import StringIO
from contextlib import closing

from libprs500.ebooks.BeautifulSoup import BeautifulStoneSoup
from libprs500.ebooks.metadata.opf import OPF, OPFReader


class EPubException(Exception):
    pass

class OCFException(EPubException):
    pass

class ContainerException(OCFException):
    pass

class Container(dict):
    def __init__(self, stream=None):
        if not stream: return
        soup = BeautifulStoneSoup(stream.read())
        container = soup.find('container')
        if not container:
            raise OCFException("<container/> element missing")
        if container.get('version', None) != '1.0':
            raise EPubException("unsupported version of OCF")
        rootfiles = container.find('rootfiles')
        if not rootfiles:
            raise EPubException("<rootfiles/> element missing")
        for rootfile in rootfiles.findAll('rootfile'):
            try:
                self[rootfile['media-type']] = rootfile['full-path']
            except KeyError:
                raise EPubException("<rootfile/> element malformed")

class OCF(object):
    MIMETYPE = 'application/epub+zip'
    CONTAINER_PATH = 'META-INF/container.xml'
    
    def __init__(self):
        raise NotImplementedError('Abstract base class')

class OCFReader(OCF):
    def __init__(self):
        try:
            mimetype = self.open('mimetype').read().rstrip()
            if mimetype != OCF.MIMETYPE:
                raise EPubException
        except (KeyError, EPubException):
            raise EPubException("not an .epub OCF container")

        try:
            with closing(self.open(OCF.CONTAINER_PATH)) as f:
                self.container = Container(f)
        except KeyError:
            raise EPubException("missing OCF container.xml file")

        try:
            with closing(self.open(self.container[OPF.MIMETYPE])) as f:
                self.opf = OPFReader(f, self.root)
        except KeyError:
            raise EPubException("missing OPF package file")

class OCFZipReader(OCFReader):
    def __init__(self, stream):
        try:
            self.archive = ZipFile(stream, 'r')
        except BadZipfile:
            raise EPubException("not a ZIP .epub OCF container")
        self.root = getattr(stream, 'name', os.getcwd())
        super(OCFZipReader, self).__init__()

    def open(self, name, mode='r'):
        return StringIO(self.archive.read(name))

class OCFDirReader(OCFReader):
    def __init__(self, path):
        self.root = path
        super(OCFDirReader, self).__init__()
        
    def open(self, path, *args, **kwargs):
        return open(os.path.join(self.root, path), *args, **kwargs)
    
    
def get_metadata(stream):
    """ Return metadata as a L{MetaInfo} object """
    return OCFZipReader(stream).opf

def main(args=sys.argv):
    if len(args) != 2 or '--help' in args or '-h' in args:
        print >>sys.stderr, 'Usage:', args[0], 'mybook.epub'
        return 1
    
    path = os.path.abspath(os.path.expanduser(args[1]))
    print unicode(get_metadata(open(path, 'rb')))
    return 0

if __name__ == '__main__':
    sys.exit(main())
