__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch Die Zeit.
'''

from calibre.web.feeds.news import BasicNewsRecipe


class ZeitDe(BasicNewsRecipe):

    title = 'Die Zeit Nachrichten'
    description = 'Die Zeit - Online Nachrichten'
    language = _('German')
    __author__ = 'Kovid Goyal and Martin Pitt'
    use_embedded_content   = False
    timefmt = ' [%d %b %Y]'
    max_articles_per_feed = 40
    no_stylesheets = True
    encoding = 'latin1'


    feeds =  [ ('Kurznachrichten', 'http://newsfeed.zeit.de/news/index'),
               ('Politik', 'http://newsfeed.zeit.de/politik/index'),
               ('Wirtschaft', 'http://newsfeed.zeit.de/wirtschaft/index'),
               ('Meinung', 'http://newsfeed.zeit.de/meinung/index'),
               ('Gesellschaft', 'http://newsfeed.zeit.de/gesellschaft/index'),
               ('Kultur', 'http://newsfeed.zeit.de/kultur/index'),
               ('Wissen', 'http://newsfeed.zeit.de/wissen/index'),
             ]

    def print_version(self,url):
        return url.replace('http://www.zeit.de/', 'http://images.zeit.de/text/').replace('?from=rss', '')

