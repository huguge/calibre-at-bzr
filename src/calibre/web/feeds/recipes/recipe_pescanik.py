#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
pescanik.net
'''

import re
from calibre.web.feeds.news import BasicNewsRecipe

class Pescanik(BasicNewsRecipe):
    title                 = 'Pescanik'
    __author__            = 'Darko Miletic'
    description           = 'Pescanik'
    publisher             = 'Pescanik'
    category              = 'news, politics, Serbia'    
    oldest_article        = 5
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    remove_javascript     = True
    encoding              = 'utf8'
    cover_url             = "http://pescanik.net/templates/ja_teline/images/logo.png"
    language              = _('Serbian')
    extra_css = '@font-face {font-family: "serif1";src:url(res:///opt/sony/ebook/FONT/tt0011m_.ttf)} @font-face {font-family: "sans1";src:url(res:///opt/sony/ebook/FONT/tt0003m_.ttf)} body{font-family: serif1, serif} .article_description{font-family: sans1, sans-serif}'
    
    html2lrf_options = [
                          '--comment'  , description
                        , '--category' , category
                        , '--publisher', publisher
                        , '--ignore-tables'
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"\nlinearize_tables=True' 
    
    
    preprocess_regexps = [(re.compile(u'\u0110'), lambda match: u'\u00D0')]
    
    remove_tags = [
                     dict(name='td'  , attrs={'class':'buttonheading'})
                    ,dict(name='span', attrs={'class':'article_seperator'})
                    ,dict(name=['object','link','img','h4','ul'])
                  ]

    feeds       = [(u'Pescanik Online', u'http://pescanik.net/index.php?option=com_rd_rss&id=12')]

    def print_version(self, url):
        nurl = url.replace('/index.php','/index2.php')        
        return nurl + '&pop=1&page=0'

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="sr-Latn-RS"/>'
        soup.head.insert(0,mtag)    
        for item in soup.findAll(style=True):
            del item['style']
        return soup
