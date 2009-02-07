#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2009, Matthew Briggs'
__docformat__ = 'restructuredtext en'

'''
http://www.theaustralian.news.com.au/
'''

from calibre.web.feeds.news import BasicNewsRecipe

class DailyTelegraph(BasicNewsRecipe):
    title          = u'The Australian'
    __author__     = u'Matthew Briggs'
    description    = u'National broadsheet newspaper from down under - colloquially known as The Oz'
    language = _('English')
    oldest_article = 2
    max_articles_per_feed = 10
    remove_javascript      = True
    no_stylesheets         = True
    encoding               = 'utf8'
    
    html2lrf_options = [
                          '--comment'       , description
                        , '--category'      , 'news, Australia'
                        , '--publisher'     , title
                        ]
    
    keep_only_tags = [
                        dict(name='h1', attrs={'class':'section-heading'})
                       ,dict(name='div', attrs={'id':'article'})
                     ]
                     
    remove_tags = [dict(name=['object','link'])]
    
    feeds          = [
                     (u'News', u'http://feeds.news.com.au/public/rss/2.0/aus_news_807.xml'),
                     (u'World News', u'http://feeds.news.com.au/public/rss/2.0/aus_world_808.xml'),
                     (u'Opinion', u'http://feeds.news.com.au/public/rss/2.0/aus_opinion_58.xml'),
                     (u'Business', u'http://feeds.news.com.au/public/rss/2.0/aus_business_811.xml'),
                     (u'Media', u'http://feeds.news.com.au/public/rss/2.0/aus_media_57.xml'),
                     (u'Higher Education', u'http://feeds.news.com.au/public/rss/2.0/aus_higher_education_56.xml'),
                     (u'The Arts', u'http://feeds.news.com.au/public/rss/2.0/aus_arts_51.xml'),
                     (u'Commercial Property', u'http://feeds.news.com.au/public/rss/2.0/aus_business_commercial_property_708.xml'),
                     (u'The Nation', u'http://feeds.news.com.au/public/rss/2.0/aus_the_nation_62.xml'),
                     (u'Sport', u'http://feeds.news.com.au/public/rss/2.0/aus_sport_61.xml'),
                     (u'Travel', u'http://feeds.news.com.au/public/rss/2.0/aus_travel_and_indulgence_63.xml'),
                     (u'Defence', u'http://feeds.news.com.au/public/rss/2.0/aus_defence_54.xml'),
                     (u'Aviation', u'http://feeds.news.com.au/public/rss/2.0/aus_business_aviation_706.xml'),
                     (u'Mining', u'http://feeds.news.com.au/public/rss/2.0/aus_business_mining_704.xml'),
                     (u'Climate', u'http://feeds.news.com.au/public/rss/2.0/aus_climate_809.xml'),
                     (u'Property', u'http://feeds.news.com.au/public/rss/2.0/aus_property_59.xml'),
                     (u'US Election', u'http://feeds.news.com.au/public/rss/2.0/aus_uselection_687.xml')
                     ]
