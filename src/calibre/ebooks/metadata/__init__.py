#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

"""
Provides abstraction for metadata reading.writing from a variety of ebook formats.
"""
import os, sys, re
from urllib import unquote, quote
from urlparse import urlparse

from calibre import relpath, guess_type, remove_bracketed_text

from calibre.utils.config import tweaks

_author_pat = re.compile(',?\s+(and|with)\s+', re.IGNORECASE)
def string_to_authors(raw):
    raw = raw.replace('&&', u'\uffff')
    raw = _author_pat.sub('&', raw)
    authors = [a.strip().replace(u'\uffff', '&') for a in raw.split('&')]
    return [a for a in authors if a]

def authors_to_string(authors):
    if authors is not None:
        return ' & '.join([a.replace('&', '&&') for a in authors if a])
    else:
        return ''

def author_to_author_sort(author, method=None):
    if not author:
        return u''
    sauthor = remove_bracketed_text(author).strip()
    tokens = sauthor.split()
    if len(tokens) < 2:
        return author
    if method is None:
        method = tweaks['author_sort_copy_method']
    if method == u'copy':
        return author
    suffixes = set([x.lower() for x in tweaks['author_name_suffixes']])
    suffixes |= set([x+u'.' for x in suffixes])

    last = tokens[-1].lower()
    suffix = None
    if last in suffixes:
        suffix = tokens[-1]
        tokens = tokens[:-1]

    if method == u'comma' and u',' in u''.join(tokens):
        return author

    atokens = tokens[-1:] + tokens[:-1]
    if suffix:
        atokens.append(suffix)

    if method != u'nocomma' and len(atokens) > 1:
        atokens[0] += u','

    return u' '.join(atokens)

def authors_to_sort_string(authors):
    return ' & '.join(map(author_to_author_sort, authors))

try:
    _title_pat = re.compile(tweaks.get('title_sort_articles',
                                       r'^(A|The|An)\s+'), re.IGNORECASE)
except:
    print 'Error in title sort pattern'
    import traceback
    traceback.print_exc()
    _title_pat = re.compile('^(A|The|An)\s+', re.IGNORECASE)

_ignore_starts = u'\'"'+u''.join(unichr(x) for x in range(0x2018, 0x201e)+[0x2032, 0x2033])

def title_sort(title, order=None):
    if order is None:
        order = tweaks['title_series_sorting']
    title = title.strip()
    if order == 'strictly_alphabetic':
        return title
    if title and title[0] in _ignore_starts:
        title = title[1:]
    match = _title_pat.search(title)
    if match:
        prep = match.group(1)
        title = title[len(prep):] + ', ' + prep
    return title.strip()

coding = zip(
[1000,900,500,400,100,90,50,40,10,9,5,4,1],
["M","CM","D","CD","C","XC","L","XL","X","IX","V","IV","I"]
)



def roman(num):
    if num <= 0 or num >= 4000 or int(num) != num:
        return str(num)
    result = []
    for d, r in coding:
        while num >= d:
            result.append(r)
            num -= d
    return ''.join(result)


def fmt_sidx(i, fmt='%.2f', use_roman=False):
    if i is None or i == '':
        i = 1
    try:
        i = float(i)
    except TypeError:
        return str(i)
    if int(i) == float(i):
        return roman(int(i)) if use_roman else '%d'%int(i)
    return fmt%i

class Resource(object):
    '''
    Represents a resource (usually a file on the filesystem or a URL pointing
    to the web. Such resources are commonly referred to in OPF files.

    They have the interface:

    :member:`path`
    :member:`mime_type`
    :method:`href`

    '''

    def __init__(self, href_or_path, basedir=os.getcwd(), is_path=True):
        self._href = None
        self._basedir = basedir
        self.path = None
        self.fragment = ''
        try:
            self.mime_type = guess_type(href_or_path)[0]
        except:
            self.mime_type = None
        if self.mime_type is None:
            self.mime_type = 'application/octet-stream'
        if is_path:
            path = href_or_path
            if not os.path.isabs(path):
                path = os.path.abspath(os.path.join(basedir, path))
            if isinstance(path, str):
                path = path.decode(sys.getfilesystemencoding())
            self.path = path
        else:
            url = urlparse(href_or_path)
            if url[0] not in ('', 'file'):
                self._href = href_or_path
            else:
                pc = url[2]
                if isinstance(pc, unicode):
                    pc = pc.encode('utf-8')
                pc = unquote(pc).decode('utf-8')
                self.path = os.path.abspath(os.path.join(basedir, pc.replace('/', os.sep)))
                self.fragment = unquote(url[-1])


    def href(self, basedir=None):
        '''
        Return a URL pointing to this resource. If it is a file on the filesystem
        the URL is relative to `basedir`.

        `basedir`: If None, the basedir of this resource is used (see :method:`set_basedir`).
        If this resource has no basedir, then the current working directory is used as the basedir.
        '''
        if basedir is None:
            if self._basedir:
                basedir = self._basedir
            else:
                basedir = os.getcwd()
        if self.path is None:
            return self._href
        f = self.fragment.encode('utf-8') if isinstance(self.fragment, unicode) else self.fragment
        frag = '#'+quote(f) if self.fragment else ''
        if self.path == basedir:
            return ''+frag
        try:
            rpath = relpath(self.path, basedir)
        except OSError: # On windows path and basedir could be on different drives
            rpath = self.path
        if isinstance(rpath, unicode):
            rpath = rpath.encode('utf-8')
        return quote(rpath.replace(os.sep, '/'))+frag

    def set_basedir(self, path):
        self._basedir = path

    def basedir(self):
        return self._basedir

    def __repr__(self):
        return 'Resource(%s, %s)'%(repr(self.path), repr(self.href()))


class ResourceCollection(object):

    def __init__(self):
        self._resources = []

    def __iter__(self):
        for r in self._resources:
            yield r

    def __len__(self):
        return len(self._resources)

    def __getitem__(self, index):
        return self._resources[index]

    def __bool__(self):
        return len(self._resources) > 0

    def __str__(self):
        resources = map(repr, self)
        return '[%s]'%', '.join(resources)

    def __repr__(self):
        return str(self)

    def append(self, resource):
        if not isinstance(resource, Resource):
            raise ValueError('Can only append objects of type Resource')
        self._resources.append(resource)

    def remove(self, resource):
        self._resources.remove(resource)

    def replace(self, start, end, items):
        'Same as list[start:end] = items'
        self._resources[start:end] = items

    @staticmethod
    def from_directory_contents(top, topdown=True):
        collection = ResourceCollection()
        for spec in os.walk(top, topdown=topdown):
            path = os.path.abspath(os.path.join(spec[0], spec[1]))
            res = Resource.from_path(path)
            res.set_basedir(top)
            collection.append(res)
        return collection

    def set_basedir(self, path):
        for res in self:
            res.set_basedir(path)



def MetaInformation(title, authors=(_('Unknown'),)):
    ''' Convenient encapsulation of book metadata, needed for compatibility
        @param title: title or ``_('Unknown')`` or a MetaInformation object
        @param authors: List of strings or []
    '''
    from calibre.ebooks.metadata.book.base import Metadata
    mi = None
    if hasattr(title, 'title') and hasattr(title, 'authors'):
        mi = title
        title = mi.title
        authors = mi.authors
    return Metadata(title, authors, other=mi)

def check_isbn10(isbn):
    try:
        digits = map(int, isbn[:9])
        products = [(i+1)*digits[i] for i in range(9)]
        check = sum(products)%11
        if (check == 10 and isbn[9] == 'X') or check == int(isbn[9]):
            return isbn
    except:
        pass
    return None

def check_isbn13(isbn):
    try:
        digits = map(int, isbn[:12])
        products = [(1 if i%2 ==0 else 3)*digits[i] for i in range(12)]
        check = 10 - (sum(products)%10)
        if check == 10:
            check = 0
        if str(check) == isbn[12]:
            return isbn
    except:
        pass
    return None

def check_isbn(isbn):
    if not isbn:
        return None
    isbn = re.sub(r'[^0-9X]', '', isbn.upper())
    all_same = re.match(r'(\d)\1{9,12}$', isbn)
    if all_same is not None:
        return None
    if len(isbn) == 10:
        return check_isbn10(isbn)
    if len(isbn) == 13:
        return check_isbn13(isbn)
    return None

