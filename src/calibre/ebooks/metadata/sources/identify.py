#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time
from datetime import datetime
from Queue import Queue, Empty
from threading import Thread
from io import BytesIO
from operator import attrgetter

from calibre.customize.ui import metadata_plugins
from calibre.ebooks.metadata.sources.base import create_log, msprefs
from calibre.ebooks.metadata.xisbn import xisbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.date import utc_tz
from calibre.utils.html2text import html2text
from calibre.utils.icu import lower

# Download worker {{{
class Worker(Thread):

    def __init__(self, plugin, kwargs, abort):
        Thread.__init__(self)
        self.daemon = True

        self.plugin, self.kwargs, self.rq = plugin, kwargs, Queue()
        self.abort = abort
        self.buf = BytesIO()
        self.log = create_log(self.buf)

    def run(self):
        start = time.time()
        try:
            self.plugin.identify(self.log, self.rq, self.abort, **self.kwargs)
        except:
            self.log.exception('Plugin', self.plugin.name, 'failed')
        self.plugin.dl_time_spent = time.time() - start

def is_worker_alive(workers):
    for w in workers:
        if w.is_alive():
            return True
    return False

# }}}

# Merge results from different sources {{{

class ISBNMerge(object):

    def __init__(self):
        self.pools = {}
        self.isbnless_results = []

    def isbn_in_pool(self, isbn):
        if isbn:
            for isbns, pool in self.pools.iteritems():
                if isbn in isbns:
                    return pool
        return None

    def pool_has_result_from_same_source(self, pool, result):
        results = pool[1]
        for r in results:
            if r.identify_plugin is result.identify_plugin:
                return True
        return False

    def add_result(self, result):
        isbn = result.isbn
        if isbn:
            pool = self.isbn_in_pool(isbn)
            if pool is None:
                isbns, min_year = xisbn.get_isbn_pool(isbn)
                if not isbns:
                    isbns = frozenset([isbn])
                self.pools[isbns] = pool = (min_year, [])

            if not self.pool_has_result_from_same_source(pool, result):
                pool[1].append(result)
        else:
            self.isbnless_results.append(result)

    def finalize(self):
        has_isbn_result = False
        for results in self.pools.itervalues():
            if results:
                has_isbn_result = True
                break
        self.has_isbn_result = has_isbn_result

        if has_isbn_result:
            self.merge_isbn_results()
        else:
            results = sorted(self.isbnless_results,
                    key=attrgetter('relevance_in_source'))
            # Pick only the most relevant result from each source
            self.results = []
            seen = set()
            for result in results:
                if result.identify_plugin not in seen:
                    seen.add(result.identify_plugin)
                    self.results.append(result)
                    result.average_source_relevance = \
                        result.relevance_in_source

        self.merge_metadata_results()

        return self.results

    def merge_metadata_results(self):
        ' Merge results with identical title and authors '
        groups = {}
        for result in self.results:
            title = lower(result.title if result.title else '')
            key = (title, tuple([lower(x) for x in result.authors]))
            if key not in groups:
                groups[key] = []
            groups[key].append(result)

        if len(groups) != len(self.results):
            self.results = []
            for rgroup in groups.itervalues():
                rel = [r.average_source_relevance for r in rgroup]
                if len(rgroup) > 1:
                    result = self.merge(rgroup, None, do_asr=False)
                    result.average_source_relevance = sum(rel)/len(rel)
                else:
                    result = rgroup[0]
                self.results.append(result)

        self.results.sort(key=attrgetter('average_source_relevance'))

    def merge_isbn_results(self):
        self.results = []
        for min_year, results in self.pools.itervalues():
            if results:
                self.results.append(self.merge(results, min_year))

        self.results.sort(key=attrgetter('average_source_relevance'))

    def length_merge(self, attr, results, null_value=None, shortest=True):
        values = [getattr(x, attr) for x in results if not x.is_null(attr)]
        values = [x for x in values if len(x) > 0]
        if not values:
            return null_value
        values.sort(key=len, reverse=not shortest)
        return values[0]

    def random_merge(self, attr, results, null_value=None):
        values = [getattr(x, attr) for x in results if not x.is_null(attr)]
        return values[0] if values else null_value

    def merge(self, results, min_year, do_asr=True):
        ans = Metadata(_('Unknown'))

        # We assume the shortest title has the least cruft in it
        ans.title = self.length_merge('title', results, null_value=ans.title)

        # No harm in having extra authors, maybe something useful like an
        # editor or translator
        ans.authors = self.length_merge('authors', results,
                null_value=ans.authors, shortest=False)

        # We assume the shortest publisher has the least cruft in it
        ans.publisher = self.length_merge('publisher', results,
                null_value=ans.publisher)

        # We assume the smallest set of tags has the least cruft in it
        ans.tags = self.length_merge('tags', results,
                null_value=ans.tags)

        # We assume the longest series has the most info in it
        ans.series = self.length_merge('series', results,
                null_value=ans.series, shortest=False)
        for r in results:
            if r.series and r.series == ans.series:
                ans.series_index = r.series_index
                break

        # Average the rating over all sources
        ratings = []
        for r in results:
            rating = r.rating
            if rating and rating > 0 and rating <= 5:
                ratings.append(rating)
        if ratings:
            ans.rating = sum(ratings)/len(ratings)

        # Smallest language is likely to be valid
        ans.language = self.length_merge('language', results,
                null_value=ans.language)

        # Choose longest comments
        ans.comments = self.length_merge('comments', results,
                null_value=ans.comments, shortest=False)

        # Published date
        if min_year:
            min_date = datetime(min_year, 1, 2, tzinfo=utc_tz)
            ans.pubdate = min_date
        else:
            min_date = datetime(3001, 1, 1, tzinfo=utc_tz)
            for r in results:
                if r.pubdate is not None and r.pubdate < min_date:
                    min_date = r.pubdate
            if min_date.year < 3000:
                ans.pubdate = min_date

        # Identifiers
        for r in results:
            ans.identifiers.update(r.identifiers)

        # Cover URL
        ans.has_cached_cover_url = bool([r for r in results if
            getattr(r, 'has_cached_cover_url', False)])

        # Merge any other fields with no special handling (random merge)
        touched_fields = set()
        for r in results:
            if hasattr(r, 'identify_plugin'):
                touched_fields |= r.identify_plugin.touched_fields

        for f in touched_fields:
            if f.startswith('identifier:') or not ans.is_null(f):
                continue
            setattr(ans, f, self.random_merge(f, results,
                null_value=getattr(ans, f)))

        if do_asr:
            avg = [x.relevance_in_source for x in results]
            avg = sum(avg)/len(avg)
            ans.average_source_relevance = avg

        return ans


def merge_identify_results(result_map, log):
    isbn_merge = ISBNMerge()
    for plugin, results in result_map.iteritems():
        for result in results:
            isbn_merge.add_result(result)

    return isbn_merge.finalize()

# }}}

def identify(log, abort, # {{{
        title=None, authors=None, identifiers={}, timeout=30):
    start_time = time.time()
    plugins = [p for p in metadata_plugins(['identify']) if p.is_configured()]

    kwargs = {
        'title': title,
        'authors': authors,
        'identifiers': identifiers,
        'timeout': timeout,
    }

    log('Running identify query with parameters:')
    log(kwargs)
    log('Using plugins:', ', '.join([p.name for p in plugins]))
    log('The log from individual plugins is below')

    workers = [Worker(p, kwargs, abort) for p in plugins]
    for w in workers:
        w.start()

    first_result_at = None
    results = {}
    for p in plugins:
        results[p] = []
    logs = dict([(w.plugin, w.buf) for w in workers])

    def get_results():
        found = False
        for w in workers:
            try:
                result = w.rq.get_nowait()
            except Empty:
                pass
            else:
                results[w.plugin].append(result)
                found = True
        return found

    wait_time = msprefs['wait_after_first_identify_result']
    while True:
        time.sleep(0.2)

        if get_results() and first_result_at is None:
            first_result_at = time.time()

        if not is_worker_alive(workers):
            break

        if (first_result_at is not None and time.time() - first_result_at >
                wait_time):
            log('Not waiting any longer for more results')
            abort.set()
            break

    while not abort.is_set() and get_results():
        pass

    sort_kwargs = dict(kwargs)
    for k in list(sort_kwargs.iterkeys()):
        if k not in ('title', 'authors', 'identifiers'):
            sort_kwargs.pop(k)

    longest, lp = -1, ''
    for plugin, presults in results.iteritems():
        presults.sort(key=plugin.identify_results_keygen(**sort_kwargs))
        plog = logs[plugin].getvalue().strip()
        log('\n'+'*'*30, plugin.name, '*'*30)
        log('Request extra headers:', plugin.browser.addheaders)
        log('Found %d results'%len(presults))
        time_spent = getattr(plugin, 'dl_time_spent', None)
        if time_spent is None:
            log('Downloading was aborted')
            longest, lp = -1, plugin.name
        else:
            log('Downloading from', plugin.name, 'took', time_spent)
            if time_spent > longest:
                longest, lp = time_spent, plugin.name
        for r in presults:
            log('\n\n---')
            log(unicode(r))
        if plog:
            log(plog)
        log('\n'+'*'*80)

        for i, result in enumerate(presults):
            result.relevance_in_source = i
            result.has_cached_cover_url = \
                plugin.get_cached_cover_url(result.identifiers) is not None
            result.identify_plugin = plugin

    log('The identify phase took %.2f seconds'%(time.time() - start_time))
    log('The longest time (%f) was taken by:'%longest, lp)
    log('Merging results from different sources and finding earliest',
            'publication dates')
    start_time = time.time()
    results = merge_identify_results(results, log)
    log('We have %d merged results, merging took: %.2f seconds' %
            (len(results), time.time() - start_time))

    if msprefs['txt_comments']:
        for r in results:
            if r.plugin.has_html_comments and r.comments:
                r.comments = html2text(r.comments)

    dummy = Metadata(_('Unknown'))
    max_tags = msprefs['max_tags']
    for r in results:
        for f in msprefs['ignore_fields']:
            setattr(r, f, getattr(dummy, f))
        r.tags = r.tags[:max_tags]

    return results
# }}}

if __name__ == '__main__': # tests {{{
    # To run these test use: calibre-debug -e
    # src/calibre/ebooks/metadata/sources/identify.py
    from calibre.ebooks.metadata.sources.test import (test_identify,
            title_test, authors_test)
    tests = [

            ( # An e-book ISBN not on Amazon, one of the authors is
              # unknown to Amazon
                {'identifiers':{'isbn': '9780307459671'},
                    'title':'Invisible Gorilla', 'authors':['Christopher Chabris']},
                [title_test('The Invisible Gorilla: And Other Ways Our Intuitions Deceive Us',
                    exact=True), authors_test(['Christopher Chabris', 'Daniel Simons'])]

            ),

            (  # Test absence of identifiers
                {'title':'Learning Python',
                    'authors':['Lutz']},
                [title_test('Learning Python',
                    exact=True), authors_test(['Mark Lutz'])
                 ]

            ),

            ( # Sophisticated comment formatting
                {'identifiers':{'isbn': '9781416580829'}},
                [title_test('Angels & Demons',
                    exact=True), authors_test(['Dan Brown'])]
            ),

            ( # No ISBN
                {'title':'Justine', 'authors':['Durrel']},
                [title_test('Justine', exact=True),
                    authors_test(['Lawrence Durrel'])]
            ),

            (  # A newer book
                {'identifiers':{'isbn': '9780316044981'}},
                [title_test('The Heroes', exact=True),
                    authors_test(['Joe Abercrombie'])]

            ),

        ]
    #test_identify(tests[1:2])
    test_identify(tests)
# }}}

