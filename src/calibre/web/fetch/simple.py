#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch a webpage and its links recursively. The webpages are saved to disk in
UTF-8 encoding with any charset declarations removed.
'''
import sys, socket, os, urlparse, re, time, copy, urllib2, threading, traceback
from urllib import url2pathname, quote
from threading import RLock
from httplib import responses
from PIL import Image
from cStringIO import StringIO

from calibre import browser, sanitize_file_name, \
                    relpath, unicode_path
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag
from calibre.ebooks.chardet import xml_to_unicode
from calibre.utils.config import OptionParser
from calibre.utils.logging import Log

class FetchError(Exception):
    pass

class closing(object):
    'Context to automatically close something at the end of a block.'

    def __init__(self, thing):
        self.thing = thing

    def __enter__(self):
        return self.thing

    def __exit__(self, *exc_info):
        try:
            self.thing.close()
        except Exception:
            pass

_browser_lock = RLock()

def basename(url):
    parts = urlparse.urlsplit(url)
    path = url2pathname(parts.path)
    res = os.path.basename(path)
    if not os.path.splitext(res)[1]:
        return 'index.html'
    return res

def save_soup(soup, target):
    ns = BeautifulSoup('<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />')
    nm = ns.find('meta')
    metas = soup.findAll('meta', content=True)
    for meta in metas:
        if 'charset' in meta.get('content', '').lower():
            meta.replaceWith(nm)

    selfdir = os.path.dirname(target)

    for tag in soup.findAll(['img', 'link', 'a']):
        for key in ('src', 'href'):
            path = tag.get(key, None)
            if path and os.path.isfile(path) and os.path.exists(path) and os.path.isabs(path):
                tag[key] = unicode_path(relpath(path, selfdir).replace(os.sep, '/'))

    html = unicode(soup)
    with open(target, 'wb') as f:
        f.write(html.encode('utf-8'))

class response(str):

    def __new__(cls, *args):
        obj = super(response, cls).__new__(cls, *args)
        obj.newurl = None
        return obj

class DummyLock(object):

    def __enter__(self, *args): return self
    def __exit__(self, *args): pass

class RecursiveFetcher(object):
    LINK_FILTER = tuple(re.compile(i, re.IGNORECASE) for i in
                ('.exe\s*$', '.mp3\s*$', '.ogg\s*$', '^\s*mailto:', '^\s*$'))
    #ADBLOCK_FILTER = tuple(re.compile(i, re.IGNORECASE) for it in
    #                       (
    #
    #                        )
    #                       )
    CSS_IMPORT_PATTERN = re.compile(r'\@import\s+url\((.*?)\)', re.IGNORECASE)
    default_timeout = socket.getdefaulttimeout() # Needed here as it is used in __del__
    DUMMY_LOCK = DummyLock()

    def __init__(self, options, log, image_map={}, css_map={}, job_info=None):
        self.base_dir = os.path.abspath(os.path.expanduser(options.dir))
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        self.log = log
        self.default_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(options.timeout)
        self.verbose = options.verbose
        self.encoding = options.encoding
        self.browser = options.browser if hasattr(options, 'browser') else browser()
        self.max_recursions = options.max_recursions
        self.match_regexps  = [re.compile(i, re.IGNORECASE) for i in options.match_regexps]
        self.filter_regexps = [re.compile(i, re.IGNORECASE) for i in options.filter_regexps]
        self.max_files = options.max_files
        self.delay = options.delay
        self.last_fetch_at = 0.
        self.filemap = {}
        self.imagemap = image_map
        self.imagemap_lock = threading.RLock()
        self.stylemap = css_map
        self.image_url_processor = None
        self.browser_lock = _browser_lock
        self.stylemap_lock = threading.RLock()
        self.downloaded_paths = []
        self.current_dir = self.base_dir
        self.files = 0
        self.preprocess_regexps  = getattr(options, 'preprocess_regexps', [])
        self.remove_tags         = getattr(options, 'remove_tags', [])
        self.remove_tags_after   = getattr(options, 'remove_tags_after', None)
        self.remove_tags_before  = getattr(options, 'remove_tags_before', None)
        self.keep_only_tags      = getattr(options, 'keep_only_tags', [])
        self.preprocess_html_ext = getattr(options, 'preprocess_html', lambda soup: soup)
        self.postprocess_html_ext= getattr(options, 'postprocess_html', None)
        self.download_stylesheets = not options.no_stylesheets
        self.show_progress = True
        self.failed_links = []
        self.job_info = job_info

    def get_soup(self, src):
        nmassage = copy.copy(BeautifulSoup.MARKUP_MASSAGE)
        nmassage.extend(self.preprocess_regexps)
        nmassage += [(re.compile(r'<!DOCTYPE .+?>', re.DOTALL), lambda m: '')] # Some websites have buggy doctype declarations that mess up beautifulsoup
        soup = BeautifulSoup(xml_to_unicode(src, self.verbose, strip_encoding_pats=True)[0], markupMassage=nmassage)

        if self.keep_only_tags:
            body = Tag(soup, 'body')
            try:
                if isinstance(self.keep_only_tags, dict):
                    self.keep_only_tags = [self.keep_only_tags]
                for spec in self.keep_only_tags:
                    for tag in soup.find('body').findAll(**spec):
                        body.insert(len(body.contents), tag)
                soup.find('body').replaceWith(body)
            except AttributeError: # soup has no body element
                pass

        def remove_beyond(tag, next):
            while tag is not None and tag.name != 'body':
                after = getattr(tag, next)
                while after is not None:
                    ns = getattr(tag, next)
                    after.extract()
                    after = ns
                tag = tag.parent

        if self.remove_tags_after is not None:
            rt = [self.remove_tags_after] if isinstance(self.remove_tags_after, dict) else self.remove_tags_after
            for spec in rt:
                tag = soup.find(**spec)
                remove_beyond(tag, 'nextSibling')

        if self.remove_tags_before is not None:
            tag = soup.find(**self.remove_tags_before)
            remove_beyond(tag, 'previousSibling')

        for kwds in self.remove_tags:
            for tag in soup.findAll(**kwds):
                tag.extract()
        return self.preprocess_html_ext(soup)


    def fetch_url(self, url):
        data = None
        self.log.debug('Fetching', url)
        delta = time.time() - self.last_fetch_at
        if  delta < self.delay:
            time.sleep(delta)
        if re.search(r'\s+|,', url) is not None:
            purl = list(urlparse.urlparse(url))
            for i in range(2, 6):
                purl[i] = quote(purl[i])
            url = urlparse.urlunparse(purl)
        with self.browser_lock:
            try:
                with closing(self.browser.open(url)) as f:
                    data = response(f.read()+f.read())
                    data.newurl = f.geturl()
            except urllib2.URLError, err:
                if hasattr(err, 'code') and responses.has_key(err.code):
                    raise FetchError, responses[err.code]
                if getattr(err, 'reason', [0])[0] == 104 or \
                    getattr(getattr(err, 'args', [None])[0], 'errno', None) == -2: # Connection reset by peer or Name or service not know
                    self.log.debug('Temporary error, retrying in 1 second')
                    time.sleep(1)
                    with closing(self.browser.open(url)) as f:
                        data = response(f.read()+f.read())
                        data.newurl = f.geturl()
                else:
                    raise err
            finally:
                self.last_fetch_at = time.time()
            return data


    def start_fetch(self, url):
        soup = BeautifulSoup(u'<a href="'+url+'" />')
        self.log.debug('Downloading')
        res = self.process_links(soup, url, 0, into_dir='')
        self.log.debug('%s saved to %s'%( url, res))
        return res

    def is_link_ok(self, url):
        for i in self.__class__.LINK_FILTER:
            if i.search(url):
                return False
        return True

    def is_link_wanted(self, url):
        if self.filter_regexps:
            for f in self.filter_regexps:
                if f.search(url):
                    return False
        if self.match_regexps:
            for m in self.match_regexps:
                if m.search(url):
                    return True
            return False
        return True

    def process_stylesheets(self, soup, baseurl):
        diskpath = unicode_path(os.path.join(self.current_dir, 'stylesheets'))
        if not os.path.exists(diskpath):
            os.mkdir(diskpath)
        for c, tag in enumerate(soup.findAll(lambda tag: tag.name.lower()in ['link', 'style'] and tag.has_key('type') and tag['type'].lower() == 'text/css')):
            if tag.has_key('href'):
                iurl = tag['href']
                if not urlparse.urlsplit(iurl).scheme:
                    iurl = urlparse.urljoin(baseurl, iurl, False)
                with self.stylemap_lock:
                    if self.stylemap.has_key(iurl):
                        tag['href'] = self.stylemap[iurl]
                        continue
                try:
                    data = self.fetch_url(iurl)
                except Exception, err:
                    self.log.exception('Could not fetch stylesheet %s'% iurl)
                    continue
                stylepath = os.path.join(diskpath, 'style'+str(c)+'.css')
                with self.stylemap_lock:
                    self.stylemap[iurl] = stylepath
                with open(stylepath, 'wb') as x:
                    x.write(data)
                tag['href'] = stylepath
            else:
                for ns in tag.findAll(text=True):
                    src = str(ns)
                    m = self.__class__.CSS_IMPORT_PATTERN.search(src)
                    if m:
                        iurl = m.group(1)
                        if not urlparse.urlsplit(iurl).scheme:
                            iurl = urlparse.urljoin(baseurl, iurl, False)
                        with self.stylemap_lock:
                            if self.stylemap.has_key(iurl):
                                ns.replaceWith(src.replace(m.group(1), self.stylemap[iurl]))
                                continue
                        try:
                            data = self.fetch_url(iurl)
                        except Exception, err:
                            self.log.exception('Could not fetch stylesheet %s'% iurl)
                            continue
                        c += 1
                        stylepath = os.path.join(diskpath, 'style'+str(c)+'.css')
                        with self.stylemap_lock:
                            self.stylemap[iurl] = stylepath
                        with open(stylepath, 'wb') as x:
                            x.write(data)
                        ns.replaceWith(src.replace(m.group(1), stylepath))



    def process_images(self, soup, baseurl):
        diskpath = unicode_path(os.path.join(self.current_dir, 'images'))
        if not os.path.exists(diskpath):
            os.mkdir(diskpath)
        c = 0
        for tag in soup.findAll(lambda tag: tag.name.lower()=='img' and tag.has_key('src')):
            iurl = tag['src']
            if callable(self.image_url_processor):
                iurl = self.image_url_processor(baseurl, iurl)
            ext  = os.path.splitext(iurl)[1]
            ext  = ext[:5]
            if not urlparse.urlsplit(iurl).scheme:
                iurl = urlparse.urljoin(baseurl, iurl, False)
            with self.imagemap_lock:
                if self.imagemap.has_key(iurl):
                    tag['src'] = self.imagemap[iurl]
                    continue
            try:
                data = self.fetch_url(iurl)
            except Exception, err:
                self.log.exception('Could not fetch image %s'% iurl)
                continue
            c += 1
            fname = sanitize_file_name('img'+str(c)+ext)
            if isinstance(fname, unicode):
                fname = fname.encode('ascii', 'replace')
            imgpath = os.path.join(diskpath, fname+'.jpg')
            try:
                im = Image.open(StringIO(data)).convert('RGBA')
                with self.imagemap_lock:
                    self.imagemap[iurl] = imgpath
                with open(imgpath, 'wb') as x:
                    im.save(x, 'JPEG')
                tag['src'] = imgpath
            except:
                traceback.print_exc()
                continue

    def absurl(self, baseurl, tag, key, filter=True):
        iurl = tag[key]
        parts = urlparse.urlsplit(iurl)
        if not parts.netloc and not parts.path:
            return None
        if not parts.scheme:
            iurl = urlparse.urljoin(baseurl, iurl, False)
        if not self.is_link_ok(iurl):
            self.log.debug('Skipping invalid link:', iurl)
            return None
        if filter and not self.is_link_wanted(iurl):
            self.log.debug('Filtered link: '+iurl)
            return None
        return iurl

    def normurl(self, url):
        parts = list(urlparse.urlsplit(url))
        parts[4] = ''
        return urlparse.urlunsplit(parts)

    def localize_link(self, tag, key, path):
        parts = urlparse.urlsplit(tag[key])
        suffix = '#'+parts.fragment if parts.fragment else ''
        tag[key] = path+suffix

    def process_return_links(self, soup, baseurl):
        for tag in soup.findAll(lambda tag: tag.name.lower()=='a' and tag.has_key('href')):
            iurl = self.absurl(baseurl, tag, 'href')
            if not iurl:
                continue
            nurl = self.normurl(iurl)
            if self.filemap.has_key(nurl):
                self.localize_link(tag, 'href', self.filemap[nurl])

    def process_links(self, soup, baseurl, recursion_level, into_dir='links'):
        res = ''
        diskpath = os.path.join(self.current_dir, into_dir)
        if not os.path.exists(diskpath):
            os.mkdir(diskpath)
        prev_dir = self.current_dir
        try:
            self.current_dir = diskpath
            tags = list(soup.findAll('a', href=True))

            for c, tag in enumerate(tags):
                if self.show_progress:
                    print '.',
                    sys.stdout.flush()
                sys.stdout.flush()
                iurl = self.absurl(baseurl, tag, 'href', filter=recursion_level != 0)
                if not iurl:
                    continue
                nurl = self.normurl(iurl)
                if self.filemap.has_key(nurl):
                    self.localize_link(tag, 'href', self.filemap[nurl])
                    continue
                if self.files > self.max_files:
                    return res
                linkdir = 'link'+str(c) if into_dir else ''
                linkdiskpath = os.path.join(diskpath, linkdir)
                if not os.path.exists(linkdiskpath):
                    os.mkdir(linkdiskpath)
                try:
                    self.current_dir = linkdiskpath
                    dsrc = self.fetch_url(iurl)
                    newbaseurl = dsrc.newurl
                    if len(dsrc) == 0 or \
                       len(re.compile('<!--.*?-->', re.DOTALL).sub('', dsrc).strip()) == 0:
                        raise ValueError('No content at URL %s'%iurl)
                    if self.encoding is not None:
                        dsrc = dsrc.decode(self.encoding, 'ignore')
                    else:
                        dsrc = xml_to_unicode(dsrc, self.verbose)[0]

                    soup = self.get_soup(dsrc)

                    base = soup.find('base', href=True)
                    if base is not None:
                        newbaseurl = base['href']
                    self.log.debug('Processing images...')
                    self.process_images(soup, newbaseurl)
                    if self.download_stylesheets:
                        self.process_stylesheets(soup, newbaseurl)

                    _fname = basename(iurl)
                    if not isinstance(_fname, unicode):
                        _fname.decode('latin1', 'replace')
                    _fname = _fname.encode('ascii', 'replace').replace('%', '').replace(os.sep, '')
                    _fname = sanitize_file_name(_fname)
                    _fname = os.path.splitext(_fname)[0]+'.xhtml'
                    res = os.path.join(linkdiskpath, _fname)
                    self.downloaded_paths.append(res)
                    self.filemap[nurl] = res
                    if recursion_level < self.max_recursions:
                        self.log.debug('Processing links...')
                        self.process_links(soup, newbaseurl, recursion_level+1)
                    else:
                        self.process_return_links(soup, newbaseurl)
                        self.log.debug('Recursion limit reached. Skipping links in', iurl)

                    if callable(self.postprocess_html_ext):
                        soup = self.postprocess_html_ext(soup,
                                c==0 and recursion_level==0 and not getattr(self, 'called_first', False),
                                self.job_info)

                        if c==0 and recursion_level == 0:
                            self.called_first = True

                    save_soup(soup, res)
                    self.localize_link(tag, 'href', res)
                except Exception, err:
                    self.failed_links.append((iurl, traceback.format_exc()))
                    self.log.exception('Could not fetch link', iurl)
                finally:
                    self.current_dir = diskpath
                    self.files += 1
        finally:
            self.current_dir = prev_dir
        if self.show_progress:
            print
        return res

    def __del__(self):
        dt = getattr(self, 'default_timeout', None)
        if dt is not None:
            socket.setdefaulttimeout(dt)

def option_parser(usage=_('%prog URL\n\nWhere URL is for example http://google.com')):
    parser = OptionParser(usage=usage)
    parser.add_option('-d', '--base-dir',
                      help=_('Base directory into which URL is saved. Default is %default'),
                      default='.', type='string', dest='dir')
    parser.add_option('-t', '--timeout',
                      help=_('Timeout in seconds to wait for a response from the server. Default: %default s'),
                      default=10.0, type='float', dest='timeout')
    parser.add_option('-r', '--max-recursions', default=1,
                      help=_('Maximum number of levels to recurse i.e. depth of links to follow. Default %default'),
                      type='int', dest='max_recursions')
    parser.add_option('-n', '--max-files', default=sys.maxint, type='int', dest='max_files',
                      help=_('The maximum number of files to download. This only applies to files from <a href> tags. Default is %default'))
    parser.add_option('--delay', default=0, dest='delay', type='int',
                      help=_('Minimum interval in seconds between consecutive fetches. Default is %default s'))
    parser.add_option('--encoding', default=None,
                      help=_('The character encoding for the websites you are trying to download. The default is to try and guess the encoding.'))
    parser.add_option('--match-regexp', default=[], action='append', dest='match_regexps',
                      help=_('Only links that match this regular expression will be followed. This option can be specified multiple times, in which case as long as a link matches any one regexp, it will be followed. By default all links are followed.'))
    parser.add_option('--filter-regexp', default=[], action='append', dest='filter_regexps',
                      help=_('Any link that matches this regular expression will be ignored. This option can be specified multiple times, in which case as long as any regexp matches a link, it will be ignored.By default, no links are ignored. If both --filter-regexp and --match-regexp are specified, then --filter-regexp is applied first.'))
    parser.add_option('--dont-download-stylesheets', action='store_true', default=False,
                      help=_('Do not download CSS stylesheets.'), dest='no_stylesheets')
    parser.add_option('--verbose', help=_('Show detailed output information. Useful for debugging'),
                      default=False, action='store_true', dest='verbose')
    return parser


def create_fetcher(options, image_map={}, log=None):
    if log is None:
        log = Log()
    return RecursiveFetcher(options, log, image_map={})

def main(args=sys.argv):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1

    fetcher = create_fetcher(options)
    fetcher.start_fetch(args[1])


if __name__ == '__main__':
    sys.exit(main())
