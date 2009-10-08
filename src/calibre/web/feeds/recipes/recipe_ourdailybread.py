#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
rbc.org
'''

from calibre.web.feeds.news import BasicNewsRecipe

class OurDailyBread(BasicNewsRecipe):
    title                 = 'Our Daily Bread'
    __author__            = 'Darko Miletic and Sujata Raman'
    description           = 'Religion'
    oldest_article        = 15
    language = 'en'
    lang = 'en'

    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    category              = 'religion'
    encoding              = 'utf-8'
    extra_css             = ' #devoTitle{font-size: x-large; font-weight: bold} '

    conversion_options = {
                             'comments'    : description
                            ,'tags'        : category
                            ,'language'    : 'en'
                         }

    keep_only_tags = [dict(name='div', attrs={'class':['altbg','text']})]

    remove_tags = [dict(name='div', attrs={'id':['ctl00_cphPrimary_pnlBookCover']}),
                   dict(name='div', attrs={'class':['devotionalLinks']})
                   ]
    extra_css = '''
                .text{font-family:Arial,Helvetica,sans-serif;font-size:x-small;}
                .devotionalTitle{font-family:Arial,Helvetica,sans-serif; font-size:large; font-weight: bold;}
                .devotionalDate{font-family:Arial,Helvetica,sans-serif; font-size:xx-small;}
                .devotionalVerse{font-family:Arial,Helvetica,sans-serif; font-size:xx-small; }
                '''

    feeds          = [(u'Our Daily Bread', u'http://www.rbc.org/rss.ashx?id=50398')]

    def preprocess_html(self, soup):
        soup.html['xml:lang'] = self.lang
        soup.html['lang']     = self.lang
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=' + self.encoding + '">'
        soup.head.insert(0,mtag)

        return self.adeify_images(soup)

    def get_cover_url(self):

        href =  'http://www.rbc.org/index.aspx'

        soup = self.index_to_soup(href)
        a = soup.find('a',attrs={'id':'ctl00_hlTodaysDevotionalImage'})

        if a :
           cover_url = a.img['src']

        return cover_url
