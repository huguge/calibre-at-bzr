# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
import urllib2
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

class KoboStore(BasicStoreConfig, StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        settings = self.get_settings()

        m_url = 'http://www.dpbolvw.net/'
        h_click = 'click-4879827-10755858'
        d_click = 'click-4879827-10772898'
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            #h_click = ''
            #d_click = ''
            pass
        
        url = m_url + h_click
        detail_url = None
        if detail_item:
            detail_url = m_url + d_click + detail_item

        if external or settings.get(self.name + '_open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_url if detail_url else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_url)
            d.setWindowTitle(self.name)
            d.set_tags(settings.get(self.name + '_tags', ''))
            d = d.exec_()

    def search(self, query, max_results=10, timeout=60):
        url = 'http://www.kobobooks.com/search/search.html?q=' + urllib2.quote(query)
        
        br = browser()
        
        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read())
            for data in doc.xpath('//ul[@class="SCShortCoverList"]/li'):
                if counter <= 0:
                    break

                id = ''.join(data.xpath('.//div[@class="SearchImageContainer"]/a[1]/@href'))
                if not id:
                    continue

                price = ''.join(data.xpath('.//span[@class="SCOurPrice"]/strong/text()'))
                if not price:
                    price = '$0.00'
                
                cover_url = ''.join(data.xpath('.//div[@class="SearchImageContainer"]//img[1]/@src'))
                
                title = ''.join(data.xpath('.//div[@class="SCItemHeader"]/h1/a[1]/text()'))
                author = ''.join(data.xpath('.//div[@class="SCItemSummary"]/span/a[1]/text()'))

                counter -= 1
                
                s = SearchResult()
                s.cover_url = cover_url
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = '?url=http://www.kobobooks.com/' + id.strip()
                
                yield s
