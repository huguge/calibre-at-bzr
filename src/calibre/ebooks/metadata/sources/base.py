#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, threading
from future_builtins import map

from calibre import browser, random_user_agent
from calibre.customize import Plugin
from calibre.utils.logging import ThreadSafeLog, FileStream
from calibre.utils.config import JSONConfig
from calibre.utils.titlecase import titlecase
from calibre.ebooks.metadata import check_isbn

msprefs = JSONConfig('metadata_sources.json')
msprefs.defaults['txt_comments'] = False
msprefs.defaults['ignore_fields'] = []
msprefs.defaults['max_tags'] = 10

def create_log(ostream=None):
    log = ThreadSafeLog(level=ThreadSafeLog.DEBUG)
    log.outputs = [FileStream(ostream)]
    return log

# Comparing Metadata objects for relevance {{{
words = ("the", "a", "an", "of", "and")
prefix_pat = re.compile(r'^(%s)\s+'%("|".join(words)))
trailing_paren_pat = re.compile(r'\(.*\)$')
whitespace_pat = re.compile(r'\s+')

def cleanup_title(s):
    if not s:
        s = _('Unknown')
    s = s.strip().lower()
    s = prefix_pat.sub(' ', s)
    s = trailing_paren_pat.sub('', s)
    s = whitespace_pat.sub(' ', s)
    return s.strip()

class InternalMetadataCompareKeyGen(object):

    '''
    Generate a sort key for comparison of the relevance of Metadata objects,
    given a search query.

    The sort key ensures that an ascending order sort is a sort by order of
    decreasing relevance.

    The algorithm is:

        * Prefer results that have the same ISBN as specified in the query
        * Prefer results with a cached cover URL
        * Prefer results with all available fields filled in
        * Prefer results that are an exact title match to the query
        * Prefer results with longer comments (greater than 10% longer)
        * Use the relevance of the result as reported by the metadata source's search
           engine
    '''

    def __init__(self, mi, source_plugin, title, authors, identifiers):
        isbn = 1 if mi.isbn and mi.isbn == identifiers.get('isbn', None) else 2

        all_fields = 1 if source_plugin.test_fields(mi) is None else 2

        exact_title = 1 if title and \
                cleanup_title(title) == cleanup_title(mi.title) else 2

        has_cover = 2 if source_plugin.get_cached_cover_url(mi.identifiers)\
                is None else 1

        self.base = (isbn, has_cover, all_fields, exact_title)
        self.comments_len = len(mi.comments.strip() if mi.comments else '')
        self.extra = (getattr(mi, 'source_relevance', 0), )

    def __cmp__(self, other):
        result = cmp(self.base, other.base)
        if result == 0:
            # Now prefer results with the longer comments, within 10%
            cx, cy = self.comments_len, other.comments_len
            t = (cx + cy) / 20
            delta = cy - cx
            if abs(delta) > t:
                result = delta
            else:
                result = cmp(self.extra, other.extra)
        return result

# }}}

class Source(Plugin):

    type = _('Metadata source')
    author = 'Kovid Goyal'

    supported_platforms = ['windows', 'osx', 'linux']

    #: Set of capabilities supported by this plugin.
    #: Useful capabilities are: 'identify', 'cover'
    capabilities = frozenset()

    #: List of metadata fields that can potentially be download by this plugin
    #: during the identify phase
    touched_fields = frozenset()

    #: Set this to True if your plugin return HTML formatted comments
    has_html_comments = False

    def __init__(self, *args, **kwargs):
        Plugin.__init__(self, *args, **kwargs)
        self._isbn_to_identifier_cache = {}
        self._identifier_to_cover_url_cache = {}
        self.cache_lock = threading.RLock()
        self._config_obj = None
        self._browser = None

    # Configuration {{{

    @property
    def prefs(self):
        if self._config_obj is None:
            self._config_obj = JSONConfig('metadata_sources/%s.json'%self.name)
        return self._config_obj
    # }}}

    # Browser {{{

    @property
    def browser(self):
        if self._browser is None:
            self._browser = browser(user_agent=random_user_agent())
        return self._browser.clone_browser()

    # }}}

    # Caching {{{

    def get_related_isbns(self, id_):
        with self.cache_lock:
            for isbn, q in self._isbn_to_identifier_cache.iteritems():
                if q == id_:
                    yield isbn

    def cache_isbn_to_identifier(self, isbn, identifier):
        with self.cache_lock:
            self._isbn_to_identifier_cache[isbn] = identifier

    def cached_isbn_to_identifier(self, isbn):
        with self.cache_lock:
            return self._isbn_to_identifier_cache.get(isbn, None)

    def cache_identifier_to_cover_url(self, id_, url):
        with self.cache_lock:
            self._identifier_to_cover_url_cache[id_] = url

    def cached_identifier_to_cover_url(self, id_):
        with self.cache_lock:
            return self._identifier_to_cover_url_cache.get(id_, None)

    # }}}

    # Utility functions {{{

    def get_author_tokens(self, authors, only_first_author=True):
        '''
        Take a list of authors and return a list of tokens useful for an
        AND search query. This function tries to return tokens in
        first name middle names last name order, by assuming that if a comma is
        in the author name, the name is in lastname, other names form.
        '''

        if authors:
            # Leave ' in there for Irish names
            pat = re.compile(r'[-,:;+!@#$%^&*(){}.`~"\s\[\]/]')
            if only_first_author:
                authors = authors[:1]
            for au in authors:
                parts = au.split()
                if ',' in au:
                    # au probably in ln, fn form
                    parts = parts[1:] + parts[:1]
                for tok in parts:
                    tok = pat.sub('', tok).strip()
                    if len(tok) > 2 and tok.lower() not in ('von', ):
                        yield tok


    def get_title_tokens(self, title):
        '''
        Take a title and return a list of tokens useful for an AND search query.
        Excludes connectives and punctuation.
        '''
        if title:
            pat = re.compile(r'''[-,:;+!@#$%^&*(){}.`~"'\s\[\]/]''')
            title = pat.sub(' ', title)
            tokens = title.split()
            for token in tokens:
                token = token.strip()
                if token and token.lower() not in ('a', 'and', 'the'):
                    yield token

    def split_jobs(self, jobs, num):
        'Split a list of jobs into at most num groups, as evenly as possible'
        groups = [[] for i in range(num)]
        jobs = list(jobs)
        while jobs:
            for gr in groups:
                try:
                    job = jobs.pop()
                except IndexError:
                    break
                gr.append(job)
        return [g for g in groups if g]

    def test_fields(self, mi):
        '''
        Return the first field from self.touched_fields that is null on the
        mi object
        '''
        for key in self.touched_fields:
            if key.startswith('identifier:'):
                key = key.partition(':')[-1]
                if not mi.has_identifier(key):
                    return 'identifier: ' + key
            elif mi.is_null(key):
                return key

    def clean_downloaded_metadata(self, mi):
        '''
        Call this method in your plugin's identify method to normalize metadata
        before putting the Metadata object into result_queue. You can of
        course, use a custom algorithm suited to your metadata source.
        '''
        def fixcase(x):
            if x:
                x = titlecase(x)
            return x
        if mi.title:
            mi.title = fixcase(mi.title)
        mi.authors = list(map(fixcase, mi.authors))
        mi.tags = list(map(fixcase, mi.tags))
        mi.isbn = check_isbn(mi.isbn)

    # }}}

    # Metadata API {{{

    def get_cached_cover_url(self, identifiers):
        '''
        Return cached cover URL for the book identified by
        the identifiers dict or None if no such URL exists.

        Note that this method must only return validated URLs, i.e. not URLS
        that could result in a generic cover image or a not found error.
        '''
        return None

    def identify_results_keygen(self, title=None, authors=None,
            identifiers={}):
        '''
        Return a function that is used to generate a key that can sort Metadata
        objects by their relevance given a search query (title, authors,
        identifiers).

        These keys are used to sort the results of a call to :meth:`identify`.

        For details on the default algorithm see
        :class:`InternalMetadataCompareKeyGen`. Re-implement this function in
        your plugin if the default algorithm is not suitable.
        '''
        def keygen(mi):
            return InternalMetadataCompareKeyGen(mi, self, title, authors,
                identifiers)
        return keygen

    def identify(self, log, result_queue, abort, title=None, authors=None,
            identifiers={}, timeout=30):
        '''
        Identify a book by its title/author/isbn/etc.

        If identifiers(s) are specified and no match is found and this metadata
        source does not store all related identifiers (for example, all ISBNs
        of a book), this method should retry with just the title and author
        (assuming they were specified).

        If this metadata source also provides covers, the URL to the cover
        should be cached so that a subsequent call to the get covers API with
        the same ISBN/special identifier does not need to get the cover URL
        again. Use the caching API for this.

        Every Metadata object put into result_queue by this method must have a
        `source_relevance` attribute that is an integer indicating the order in
        which the results were returned by the metadata source for this query.
        This integer will be used by :meth:`compare_identify_results`. If the
        order is unimportant, set it to zero for every result.

        Make sure that any cover/isbn mapping information is cached before the
        Metadata object is put into result_queue.

        :param log: A log object, use it to output debugging information/errors
        :param result_queue: A result Queue, results should be put into it.
                            Each result is a Metadata object
        :param abort: If abort.is_set() returns True, abort further processing
                      and return as soon as possible
        :param title: The title of the book, can be None
        :param authors: A list of authors of the book, can be None
        :param identifiers: A dictionary of other identifiers, most commonly
                            {'isbn':'1234...'}
        :param timeout: Timeout in seconds, no network request should hang for
                        longer than timeout.
        :return: None if no errors occurred, otherwise a unicode representation
                 of the error suitable for showing to the user

        '''
        return None

    def download_cover(self, log, result_queue, abort,
            title=None, authors=None, identifiers={}, timeout=30):
        '''
        Download a cover and put it into result_queue. The parameters all have
        the same meaning as for :meth:`identify`.

        This method should use cached cover URLs for efficiency whenever
        possible. When cached data is not present, most plugins simply call
        identify and use its results.
        '''
        pass

    # }}}

