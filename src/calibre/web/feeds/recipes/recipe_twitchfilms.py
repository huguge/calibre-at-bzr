#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
twitchfilm.net/site/
'''
from calibre.web.feeds.news import BasicNewsRecipe
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag

class Twitchfilm(BasicNewsRecipe):
    title                 = 'Twitch Films'
    __author__            = 'Darko Miletic'
    description           = 'Twitch specializes in spreading the news on strange little films from around the world.'
    oldest_article        = 30
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = True
    encoding              = 'utf-8'
    publisher             = 'Twitch'
    category              = 'twitch, twitchfilm, movie news, movie reviews, cult cinema, independent cinema, anime, foreign cinema, geek talk'
    language              = _('English')

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]

    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"'

    remove_tags = [dict(name='div', attrs={'class':'feedflare'})]

    feeds = [(u'News', u'http://feedproxy.google.com/TwitchEverything')]

    def preprocess_html(self, soup):
        mtag = Tag(soup,'meta',[('http-equiv','Content-Type'),('context','text/html; charset=utf-8')])
        soup.head.insert(0,mtag)
        soup.html['lang'] = 'en-US'
        return soup

