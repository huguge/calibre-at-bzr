#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
ft.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class FinancialTimes(BasicNewsRecipe):
    title                 = u'Financial Times'
    __author__            = 'Darko Miletic'
    description           = 'Financial world news'
    oldest_article        = 2
    language = _('English')
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    needs_subscription    = True
    simultaneous_downloads= 1
    delay                 = 1
    LOGIN = 'https://registration.ft.com/registration/barrier/login'
    
    def get_browser(self):
        br = BasicNewsRecipe.get_browser()
        if self.username is not None and self.password is not None:
            br.open(self.LOGIN)
            br.select_form(name='loginForm')
            br['username'] = self.username
            br['password'] = self.password
            br.submit()
        return br
    
    keep_only_tags    = [ dict(name='div', attrs={'id':'cont'}) ]
    remove_tags_after = dict(name='p', attrs={'class':'copyright'})
    remove_tags = [
                     dict(name='div', attrs={'id':'floating-con'})
                  ]
    
    feeds = [ 
               (u'UK'         , u'http://www.ft.com/rss/home/uk'        ) 
              ,(u'US'         , u'http://www.ft.com/rss/home/us'        ) 
              ,(u'Asia'       , u'http://www.ft.com/rss/home/asia'      ) 
              ,(u'Middle East', u'http://www.ft.com/rss/home/middleeast') 
            ]

    def preprocess_html(self, soup):
        content_type = soup.find('meta', {'http-equiv':'Content-Type'})
        if content_type:
            content_type['content'] = 'text/html; charset=utf-8'
        return soup