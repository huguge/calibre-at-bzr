#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Fetch metadata using Overdrive Content Reserve
'''
import sys, re, random, urllib, mechanize, copy
from threading import RLock
from Queue import Queue, Empty

from lxml import html, etree
from lxml.html import soupparser

from calibre import browser
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.chardet import xml_to_unicode
from calibre.library.comments import sanitize_comments_html

ovrdrv_data_cache = {}
cover_url_cache = {}
cache_lock = RLock()
base_url = 'http://search.overdrive.com/'


class OverDrive(Source):

    name = 'Overdrive'
    description = _('Downloads metadata from Overdrive\'s Content Reserve')

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'tags', 'pubdate',
        'comments', 'publisher', 'identifier:isbn', 'series', 'series_num',
        'language', 'identifier:overdrive'])
    has_html_comments = True
    supports_gzip_transfer_encoding = False
    cached_cover_url_is_reliable = True

    def identify(self, log, result_queue, abort, title=None, authors=None, # {{{
            identifiers={}, timeout=30):
        ovrdrv_id = identifiers.get('overdrive', None)
        isbn = identifiers.get('isbn', None)

        br = self.browser
        print "in identify, calling to_ovrdrv_data"
        ovrdrv_data = self.to_ovrdrv_data(br, title, authors, ovrdrv_id)
        if ovrdrv_data:
            title = ovrdrv_data[8]
            authors = ovrdrv_data[6]
            mi = Metadata(title, authors)
            self.parse_search_results(ovrdrv_data, mi)
            if ovrdrv_id is None:
                ovrdrv_id = ovrdrv_data[7]
            if isbn is not None:
                self.cache_isbn_to_identifier(isbn, ovrdrv_id)
    
            self.get_book_detail(br, ovrdrv_data[1], mi, ovrdrv_id, log)
    
            result_queue.put(mi)

        return None
    # }}}


    def get_book_url(self, identifiers): # {{{
        ovrdrv_id = identifiers.get('overdrive', None)
        if ovrdrv_id is not None:
            ovrdrv_data = ovrdrv_data_cache.get(ovrdrv_id, None)
            if ovrdrv_data:
                return ovrdrv_data[1]
            else:
                br = browser()
                ovrdrv_data = self.to_ovrdrv_data(br, None, None, ovrdrv_id)
                return ovrdrv_data[1]
    # }}}

    def download_cover(self, log, result_queue, abort, # {{{
            title=None, authors=None, identifiers={}, timeout=30):
        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            log.info('No cached cover found, running identify')
            rq = Queue()
            print "inside download cover, calling identify"
            self.identify(log, rq, abort, title=title, authors=authors,
                    identifiers=identifiers)
            if abort.is_set():
                return
            results = []
            while True:
                try:
                    results.append(rq.get_nowait())
                except Empty:
                    break
            results.sort(key=self.identify_results_keygen(
                title=title, authors=authors, identifiers=identifiers))
            for mi in results:
                cached_url = self.get_cached_cover_url(mi.identifiers)
                if cached_url is not None:
                    break
        if cached_url is None:
            log.info('No cover found')
            return

        if abort.is_set():
            return

        ovrdrv_id = identifiers.get('overdrive', None)
        br = self.browser
        referer = self.get_base_referer()+'ContentDetails-Cover.htm?ID='+ovrdrv_id
        print "downloading cover, referer is "+str(referer)
        req = mechanize.Request(cached_url)
        req.add_header('referer', referer)
        log('Downloading cover from:', cached_url)
        try:
            cdata = br.open_novisit(req, timeout=timeout).read()
            result_queue.put((self, cdata))
        except:
            log.exception('Failed to download cover from:', cached_url)
    # }}}

    def get_cached_cover_url(self, identifiers): # {{{
        url = None
        ovrdrv_id = identifiers.get('overdrive', None)
        print "inside get_cached_cover_url, ovrdrv_id is "+str(ovrdrv_id)
        if ovrdrv_id is None:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                ovrdrv_id = self.cached_isbn_to_identifier(isbn)
        if ovrdrv_id is not None:
            url = self.cached_identifier_to_cover_url(ovrdrv_id)

        return url
    # }}}

    def create_query(self, title=None, authors=None, identifiers={}):
        q = ''
        if title or authors:
            def build_term(prefix, parts):
                return ' '.join('in'+prefix + ':' + x for x in parts)
            title_tokens = list(self.get_title_tokens(title, False, True))
            if title_tokens:
                q += build_term('title', title_tokens)
            author_tokens = self.get_author_tokens(authors,
                    only_first_author=True)
            if author_tokens:
                q += ('+' if q else '') + build_term('author',
                        author_tokens)
    
        if isinstance(q, unicode):
            q = q.encode('utf-8')
        if not q:
            return None
        return BASE_URL+urlencode({
            'q':q,
            })

    def get_base_referer(self): # to be used for passing referrer headers to cover download
        choices = [
            'http://overdrive.chipublib.org/82DC601D-7DDE-4212-B43A-09D821935B01/10/375/en/',
            'http://emedia.clevnet.org/9D321DAD-EC0D-490D-BFD8-64AE2C96ECA8/10/241/en/',
            'http://singapore.lib.overdrive.com/F11D55BE-A917-4D63-8111-318E88B29740/10/382/en/',
            'http://ebooks.nypl.org/20E48048-A377-4520-BC43-F8729A42A424/10/257/en/',
            'http://spl.lib.overdrive.com/5875E082-4CB2-4689-9426-8509F354AFEF/10/335/en/'
        ]
        return choices[random.randint(0, len(choices)-1)]
    
    def format_results(self, reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid):
        fix_slashes = re.compile(r'\\/')
        thumbimage = fix_slashes.sub('/', thumbimage)
        worldcatlink = fix_slashes.sub('/', worldcatlink)
        cover_url = re.sub('(?P<img>(Ima?g(eType-)?))200', '\g<img>100', thumbimage)
        social_metadata_url = base_url+'TitleInfo.aspx?ReserveID='+reserveid+'&FormatID='+formatid
        series_num = ''
        if not series:
            if subtitle:
                title = od_title+': '+subtitle
            else:
                title = od_title
        else:
            title = od_title
            m = re.search("([0-9]+$)", subtitle)
            if m:
                series_num = float(m.group(1))
        return [cover_url, social_metadata_url, worldcatlink, series, series_num, publisher, creators, reserveid, title]
    
    def safe_query(self, br, query_url, post=''):
        '''
        The query must be initialized by loading an empty search results page
        this page attempts to set a cookie that Mechanize doesn't like
        copy the cookiejar to a separate instance and make a one-off request with the temp cookiejar
        '''
        goodcookies = br._ua_handlers['_cookies'].cookiejar
        clean_cj = mechanize.CookieJar()
        cookies_to_copy = []
        for cookie in goodcookies:
            copied_cookie = copy.deepcopy(cookie)
            cookies_to_copy.append(copied_cookie)
        for copied_cookie in cookies_to_copy:
            clean_cj.set_cookie(copied_cookie)

        if post:
            br.open_novisit(query_url, post)
        else:
            br.open_novisit(query_url)

        br.set_cookiejar(clean_cj)


    def overdrive_search(self, br, q, title, author):
        # re-initialize the cookiejar to so that it's clean
        clean_cj = mechanize.CookieJar()
        br.set_cookiejar(clean_cj)
        q_query = q+'default.aspx/SearchByKeyword'
        q_init_search = q+'SearchResults.aspx'
        # get first author as string - convert this to a proper cleanup function later
        s = Source(None)
        print "printing list with author "+str(author)+":"
        author_tokens = list(s.get_author_tokens(author))
        print list(author_tokens)
        title_tokens = list(s.get_title_tokens(title, False, True))
        print "there are "+str(len(title_tokens))+" title tokens"
        for token in title_tokens:
            print "cleaned up title token is: "+str(token)
    
        if len(title_tokens) >= len(author_tokens):
            initial_q = ' '.join(title_tokens)
            xref_q = '+'.join(author_tokens)
        else:
            initial_q = ' '.join(author_tokens)
            xref_q = '+'.join(title_tokens)
    
        print "initial query is "+str(initial_q)
        print "cross reference query is "+str(xref_q)
        q_xref = q+'SearchResults.svc/GetResults?iDisplayLength=50&sSearch='+xref_q
        query = '{"szKeyword":"'+initial_q+'"}'
    
        # main query, requires specific Content Type header
        req = mechanize.Request(q_query)
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        br.open_novisit(req, query)
    
        print "q_init_search is "+q_init_search
        # initiate the search without messing up the cookiejar
        self.safe_query(br, q_init_search)
    
        # get the search results object
        results = False
        while results == False:
            xreq = mechanize.Request(q_xref)
            xreq.add_header('X-Requested-With', 'XMLHttpRequest')
            xreq.add_header('Referer', q_init_search)
            xreq.add_header('Accept', 'application/json, text/javascript, */*')
            raw = br.open_novisit(xreq).read()
            print "overdrive search result is:\n"+raw
            for m in re.finditer(ur'"iTotalDisplayRecords":(?P<displayrecords>\d+).*?"iTotalRecords":(?P<totalrecords>\d+)', raw):
                if int(m.group('displayrecords')) >= 1:
                    results = True
                elif int(m.group('totalrecords')) >= 1:
                    xref_q = ''
                    q_xref = q+'SearchResults.svc/GetResults?iDisplayLength=50&sSearch='+xref_q
                elif int(m.group('totalrecords')) == 0:
                    return ''

        print "\n\nsorting results"
        return self.sort_ovrdrv_results(raw, title, title_tokens, author, author_tokens)
    
    
    def sort_ovrdrv_results(self, raw, title=None, title_tokens=None, author=None, author_tokens=None, ovrdrv_id=None):
        print "\ntitle to search for is "+str(title)+"\nauthor to search for is "+str(author)
        close_matches = []
        raw = re.sub('.*?\[\[(?P<content>.*?)\]\].*', '[[\g<content>]]', raw)
        results = eval(raw)
        print "\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n"
        #print results
        # The search results are either from a keyword search or a multi-format list from a single ID,
        # sort through the results for closest match/format
        if results:
            for reserveid, od_title, subtitle, edition, series, publisher, format, formatid, creators, \
                    thumbimage, shortdescription, worldcatlink, excerptlink, creatorfile, sorttitle, \
                    availabletolibrary, availabletoretailer, relevancyrank, unknown1, unknown2, unknown3 in results:
                print "this record's title is "+od_title+", subtitle is "+subtitle+", author[s] are "+creators+", series is "+series
                if ovrdrv_id is not None and int(formatid) in [1, 50, 410, 900]:
                    print "overdrive id is not None, searching based on format type priority"
                    return self.format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid)            
                else:
                    creators = creators.split(', ')
                    print "split creators from results are: "+str(creators)
                    # if an exact match in a preferred format occurs
                    if creators[0] == author[0] and od_title == title and int(formatid) in [1, 50, 410, 900]:
                        print "Got Exact Match!!!"
                        return self.format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid)
                    else:
                        close_title_match = False
                        close_author_match = False
                        print "format id is "+str(formatid)
                        for token in title_tokens:
                            print "attempting to find "+str(token)+" title token"
                            if od_title.lower().find(token.lower()) != -1:
                                print "matched token"
                                close_title_match = True
                            else:
                                print "token didn't match"
                                close_title_match = False
                                break
                        for token in author_tokens:
                            print "attempting to find "+str(token)+" author token"
                            if creators[0].lower().find(token.lower()) != -1:
                                print "matched token"
                                close_author_match = True
                            else:
                                print "token didn't match"
                                close_author_match = False
                                break
                        if close_title_match and close_author_match and int(formatid) in [1, 50, 410, 900]:
                            if subtitle and series:
                                close_matches.insert(0, self.format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid))
                            else:
                                close_matches.append(self.format_results(reserveid, od_title, subtitle, series, publisher, creators, thumbimage, worldcatlink, formatid))
            if close_matches:
                return close_matches[0]
            else:
                return ''
        else:
            return ''
    
    
    def overdrive_get_record(self, br, q, ovrdrv_id):
        search_url = q+'SearchResults.aspx?ReserveID={'+ovrdrv_id+'}'
        results_url = q+'SearchResults.svc/GetResults?sEcho=1&iColumns=18&sColumns=ReserveID%2CTitle%2CSubtitle%2CEdition%2CSeries%2CPublisher%2CFormat%2CFormatID%2CCreators%2CThumbImage%2CShortDescription%2CWorldCatLink%2CExcerptLink%2CCreatorFile%2CSortTitle%2CAvailableToLibrary%2CAvailableToRetailer%2CRelevancyRank&iDisplayStart=0&iDisplayLength=10&sSearch=&bEscapeRegex=true&iSortingCols=1&iSortCol_0=17&sSortDir_0=asc'
    
        # get the base url to set the proper session cookie
        br.open_novisit(q)
    
        # initialize the search
        self.safe_query(br, search_url)
    
        # get the results
        req = mechanize.Request(results_url)
        req.add_header('X-Requested-With', 'XMLHttpRequest')
        req.add_header('Referer', search_url)
        req.add_header('Accept', 'application/json, text/javascript, */*')
        raw = br.open_novisit(req)
        raw = str(list(raw))
        clean_cj = mechanize.CookieJar()
        br.set_cookiejar(clean_cj)
        return self.sort_ovrdrv_results(raw, None, None, None, ovrdrv_id)


    def find_ovrdrv_data(self, br, title, author, isbn, ovrdrv_id=None):
        print "in find_ovrdrv_data, title is "+str(title)+", author is "+str(author)+", overdrive id is "+str(ovrdrv_id)
        q = base_url
        if ovrdrv_id is None:
           return self.overdrive_search(br, q, title, author)
        else:
           return self.overdrive_get_record(br, q, ovrdrv_id)



    def to_ovrdrv_data(self, br, title=None, author=None, ovrdrv_id=None):
        '''
        Takes either a title/author combo or an Overdrive ID.  One of these
        two must be passed to this function.
        '''
        print "starting to_ovrdrv_data"
        if ovrdrv_id is not None:
            with cache_lock:
                ans = ovrdrv_data_cache.get(ovrdrv_id, None)
            if ans:
                print "inside to_ovrdrv_data, cache lookup successful, ans is "+str(ans)
                return ans
            elif ans is False:
                print "inside to_ovrdrv_data, ans returned False"
                return None
            else:
                ovrdrv_data = self.find_ovrdrv_data(br, title, author, ovrdrv_id)
        else:
            try:
                print "trying to retrieve data, running find_ovrdrv_data"
                ovrdrv_data = self.find_ovrdrv_data(br, title, author, ovrdrv_id)
                print "ovrdrv_data is "+str(ovrdrv_data)
            except:
                import traceback
                traceback.print_exc()
                ovrdrv_data = None
        print "writing results to ovrdrv_data cache"
        with cache_lock:
            ovrdrv_data_cache[ovrdrv_id] = ovrdrv_data if ovrdrv_data else False

        return ovrdrv_data if ovrdrv_data else False


    def parse_search_results(self, ovrdrv_data, mi):
        '''
        Parse the formatted search results from the initial Overdrive query and
        add the values to the metadta.
        
        The list object has these values:
        [cover_url[0], social_metadata_url[1], worldcatlink[2], series[3], series_num[4],
        publisher[5], creators[6], reserveid[7], title[8]]

        '''
        print "inside parse_search_results, writing the metadata results"
        ovrdrv_id = ovrdrv_data[7]
        mi.set_identifier('overdrive', ovrdrv_id)

        if len(ovrdrv_data[3]) > 1:
            mi.series = ovrdrv_data[3]
            if ovrdrv_data[4]:
                mi.series_index = ovrdrv_data[4]
        mi.publisher = ovrdrv_data[5]
        mi.authors = ovrdrv_data[6]
        mi.title = ovrdrv_data[8]
        cover_url = ovrdrv_data[0]
        if cover_url:
            self.cache_identifier_to_cover_url(ovrdrv_id,
                    cover_url)


    def get_book_detail(self, br, metadata_url, mi, ovrdrv_id, log):
        try:
            raw = br.open_novisit(metadata_url).read()
        except Exception, e:
            if callable(getattr(e, 'getcode', None)) and \
                    e.getcode() == 404:
                return False
            raise   
        raw = xml_to_unicode(raw, strip_encoding_pats=True,
                resolve_entities=True)[0]
        try:
            root = soupparser.fromstring(raw)
        except:
            return False

        pub_date = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblPubDate']/text()")
        lang = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblLanguage']/text()")
        subjects = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblSubjects']/text()")
        ebook_isbn = root.xpath("//td/label[@id='ctl00_ContentPlaceHolder1_lblIdentifier']/text()")
        desc = root.xpath("//div/label[@id='ctl00_ContentPlaceHolder1_lblDescription']/ancestor::div[1]")

        if pub_date:
            from calibre.utils.date import parse_date
            mi.pubdate = parse_date(pub_date[0].strip())
        if lang:
            mi.language = lang[0].strip()
            print "languages is "+str(mi.language)
        #if ebook_isbn:
        #    print "ebook isbn is "+str(ebook_isbn[0])
        #    isbn = check_isbn(ebook_isbn[0].strip())
        #    if isbn:
        #        self.cache_isbn_to_identifier(isbn, ovrdrv_id)
        #        mi.isbn = isbn
        if subjects:
            mi.tags = [tag.strip() for tag in subjects[0].split(',')]
            print "tags are "+str(mi.tags)
        if desc:
            desc = desc[0]
            desc = html.tostring(desc, method='html', encoding=unicode).strip()
            # remove all attributes from tags
            desc = re.sub(r'<([a-zA-Z0-9]+)\s[^>]+>', r'<\1>', desc)
            # Remove comments
            desc = re.sub(r'(?s)<!--.*?-->', '', desc)
            mi.comments = sanitize_comments_html(desc)

        return None


def main(args=sys.argv):
    print "running through main tests"
    import tempfile, os, time
    tdir = tempfile.gettempdir()
    br = browser()
    for ovrdrv_id, isbn, title, author in [
            #(None, '0899661343', 'On the Road', ['Jack Kerouac']), # basic test, no series, single author
            #(None, '9780061952838', 'The Fellowship of the Ring', ['J. R. R. Tolkien']), # Series test, multi-author
            #(None, '9780061952838', 'The Two Towers (The Lord of the Rings, Book II)', ['J. R. R. Tolkien']), # Series test, book 2
            #(None, '9780618153985', 'The Fellowship of the Ring (The Lord of the Rings, Part 1)', ['J.R.R. Tolkien']),
            #('57844706-20fa-4ace-b5ee-3470b1b52173', None, 'The Two Towers', ['J. R. R. Tolkien']), # Series test, w/ ovrdrv id
            #(None, '9780345505057', 'Deluge', ['Anne McCaffrey']) # Multiple authors
            #(None, None, 'Deluge', ['Anne McCaffrey']) # Empty ISBN
            #(None, None, 'On the Road', ['Jack Kerouac']), # Nonetype ISBN
            #(None, '9780345435279', 'A Caress of Twilight', ['Laurell K. Hamilton']),
            #(None, '9780606087230', 'The Omnivore\'s Dilemma : A Natural History of Four Meals', ['Michael Pollan']), # Subtitle colon
            #(None, '9780061747649', 'Mental_Floss Presents: Condensed Knowledge', ['Will Pearson', 'Mangesh Hattikudur']),
            #(None, '9781400050802', 'The Zombie Survival Guide', ['Max Brooks']), # Two books with this title by this author
            #(None, '9781775414315', 'The Worst Journey in the World / Antarctic 1910-1913', ['Apsley Cherry-Garrard']), # Garbage sub-title
            #(None, '9780440335160', 'Outlander', ['Diana Gabaldon']), # Returns lots of results to sort through to get the best match
            (None, '9780345509741', 'The Horror Stories of Robert E. Howard', ['Robert E. Howard']), # Complex title with initials/dots stripped, some results don't have a cover
            ]:
        cpath = os.path.join(tdir, title+'.jpg')
        print "cpath is "+cpath
        st = time.time()
        curl = get_cover_url(isbn, title, author, br, ovrdrv_id)
        print '\n\n Took ', time.time() - st, ' to get basic metadata\n\n'
        if curl is None:
            print 'No cover found for', title
        else:
            print "curl is "+curl
            #open(cpath, 'wb').write(br.open_novisit(curl).read())
            #print 'Cover for', title, 'saved to', cpath
        st = time.time()
        print get_social_metadata(title, author, isbn, ovrdrv_id)
        print '\n\n Took ', time.time() - st, ' to get detailed metadata\n\n'

    return 0

if __name__ == '__main__':
    sys.exit(main())
