#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time, shutil

from calibre.constants import plugins, preferred_encoding
from calibre.ebooks.metadata import MetaInformation, string_to_authors, \
    authors_to_string
from calibre.utils.ipc.job import ParallelJob
from calibre.utils.ipc.server import Server
from calibre.ptempfile import PersistentTemporaryFile

podofo, podofo_err = plugins['podofo']

class Unavailable(Exception): pass

def get_metadata(stream, cpath=None):
    if not podofo:
        raise Unavailable(podofo_err)
    pt = PersistentTemporaryFile('_podofo.pdf')
    pt.write(stream.read())
    pt.close()
    server = Server(pool_size=1)
    job = ParallelJob('read_pdf_metadata', 'Read pdf metadata',
        lambda x,y:x,  args=[pt.name, cpath])
    server.add_job(job)
    while not job.is_finished:
        time.sleep(0.1)
        job.update()

    job.update()
    server.close()
    if job.result is None:
        raise ValueError('Failed to read metadata: ' + job.details)
    title, authors, creator, ok = job.result
    if not ok:
        print 'Failed to extract cover:'
        print job.details
    if title == '_':
        title = getattr(stream, 'name', _('Unknown'))
        title = os.path.splitext(title)[0]

    mi = MetaInformation(title, authors)
    if creator:
        mi.book_producer = creator
    if os.path.exists(pt.name): os.remove(pt.name)
    if ok:
        mi.cover = cpath
    return mi

def get_metadata_quick(raw):
    p = podofo.PDFDoc()
    p.load(raw)
    title = p.title
    if not title:
        title = '_'
    author = p.author
    authors = string_to_authors(author) if author else  [_('Unknown')]
    creator = p.creator
    mi = MetaInformation(title, authors)
    if creator:
        mi.book_producer = creator
    return mi

def get_metadata_(path, cpath=None):
    p = podofo.PDFDoc()
    p.open(path)
    title = p.title
    if not title:
        title = '_'
    author = p.author
    authors = string_to_authors(author) if author else  [_('Unknown')]
    creator = p.creator
    ok = True
    try:
        if cpath is not None:
            pages = p.pages
            if pages < 1:
                raise ValueError('PDF has no pages')
            if True or pages == 1:
                shutil.copyfile(path, cpath)
            else:
                p.extract_first_page()
                p.save(cpath)
    except:
        import traceback
        traceback.print_exc()
        ok = False

    return (title, authors, creator, ok)

def prep(val):
    if not val:
        return u''
    if not isinstance(val, unicode):
        val = val.decode(preferred_encoding, 'replace')
    return val.strip()

def set_metadata(stream, mi):
    if not podofo:
        raise Unavailable(podofo_err)
    pt = PersistentTemporaryFile('_podofo.pdf')
    pt.write(stream.read())
    pt.close()
    server = Server(pool_size=1)
    job = ParallelJob('write_pdf_metadata', 'Write pdf metadata',
        lambda x,y:x,  args=[pt.name, mi.title, mi.authors, mi.book_producer])
    server.add_job(job)
    while not job.is_finished:
        time.sleep(0.1)
        job.update()

    job.update()
    server.close()
    if job.result is not None:
        stream.seek(0)
        stream.truncate()
        stream.write(job.result)
        stream.flush()
        stream.seek(0)



def set_metadata_(path, title, authors, bkp):
    p = podofo.PDFDoc()
    p.open(path)
    title = prep(title)
    touched = False
    if title:
        p.title = title
        touched = True

    author = prep(authors_to_string(authors))
    if author:
        p.author = author
        touched = True

    bkp = prep(bkp)
    if bkp:
        p.creator = bkp
        touched = True

    if touched:
        from calibre.ptempfile import TemporaryFile
        with TemporaryFile('_pdf_set_metadata.pdf') as f:
            p.save(f)
            return open(f, 'rb').read()

if __name__ == '__main__':
    f = '/tmp/t.pdf'
    import StringIO
    stream = StringIO.StringIO(open(f).read())
    mi = get_metadata(open(f))
    print
    print 'Original metadata:'
    print mi
    mi.title = 'Test title'
    mi.authors = ['Test author', 'author2']
    mi.book_producer = 'calibre'
    set_metadata(stream, mi)
    open('/tmp/x.pdf', 'wb').write(stream.getvalue())
    print
    print 'New pdf written to /tmp/x.pdf'


