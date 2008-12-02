__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch heise.
'''

from calibre.web.feeds.news import BasicNewsRecipe


class HeiseDe(BasicNewsRecipe):

    title = 'heise'
    description = 'Computernews from Germany'
    __author__ = 'Oliver Niesner'
    use_embedded_content   = False
    timefmt = ' [%d %b %Y]'
    max_articles_per_feed = 40
    no_stylesheets = True

    remove_tags = [dict(id='navi_top'),
           dict(id='navi_bottom'),
           dict(id='logo'),
           dict(id='login_suche'),
           dict(id='navi_login'),
           dict(id='navigation'),
           dict(id='breadcrumb'),
           dict(id=''),
           dict(id='sitemap'),
           dict(id='bannerzone'),
           dict(name='span', attrs={'class':'rsaquo'}),
           dict(name='div', attrs={'class':'news_logo'}),
           dict(name='p', attrs={'class':'news_option'}),
           dict(name='p', attrs={'class':'news_navi'}),
           dict(name='p', attrs={'class':'news_foren'})]
    remove_tags_after = [dict(name='p', attrs={'class':'news_foren'})]

    feeds =  [ ('heise', 'http://www.heise.de/newsticker/heise.rdf') ]



