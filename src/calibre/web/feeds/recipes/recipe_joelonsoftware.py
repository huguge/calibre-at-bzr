#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
joelonsoftware.com
'''
from calibre.web.feeds.news import BasicNewsRecipe

class Joelonsoftware(BasicNewsRecipe):
    
    title       = 'Joel on Software'
    __author__  = 'Darko Miletic'
    description = 'Painless Software Management'
    no_stylesheets = True
    use_embedded_content  = True
    
    cover_url = 'http://www.joelonsoftware.com/RssJoelOnSoftware.jpg'
    
    html2lrf_options = [  '--comment'       , description
                        , '--category'      , 'blog,software,news'
                        , '--author'        , 'Joel Spolsky'
                       ]
    
    feeds = [(u'Articles', u'http://www.joelonsoftware.com/rss.xml')]
