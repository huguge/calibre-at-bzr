#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
oglobo.globo.com
'''

from calibre.web.feeds.news import BasicNewsRecipe

class OGlobo(BasicNewsRecipe):
    title                 = 'O Globo'
    __author__            = 'Darko Miletic'
    description           = 'News from Brasil'
    publisher             = 'O Globo'
    category              = 'news, politics, Brasil'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    cover_url             = 'http://oglobo.globo.com/_img/o-globo.png'
    remove_javascript     = True
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
                        
    keep_only_tags = [dict(name='div', attrs={'id':'ltintb'})]

    remove_tags = [  
                     dict(name='script')
                    ,dict(name='object')
                    ,dict(name='form')
                    ,dict(name='div', attrs={'id':['linksPatGoogle','rdpm','cor','com','env','rcm_st']})
                    ,dict(name='div', attrs={'class':'box-zap-anu2'})
                    ,dict(name='a')
                    ,dict(name='link')
                  ]

    
    feeds = [
               (u'Todos os canais', u'http://oglobo.globo.com/rss/plantao.xml')
              ,(u'Ciencia', u'http://oglobo.globo.com/rss/plantaociencia.xml')
              ,(u'Educacao', u'http://oglobo.globo.com/rss/plantaoeducacao.xml')
              ,(u'Opiniao', u'http://oglobo.globo.com/rss/plantaoopiniao.xml')
              ,(u'Sao Paulo', u'http://oglobo.globo.com/rss/plantaosaopaulo.xml')
              ,(u'Viagem', u'http://oglobo.globo.com/rss/plantaoviagem.xml')
              ,(u'Cultura', u'http://oglobo.globo.com/rss/plantaocultura.xml')
              ,(u'Esportes', u'http://oglobo.globo.com/rss/plantaoesportes.xml')
              ,(u'Mundo', u'http://oglobo.globo.com/rss/plantaomundo.xml')
              ,(u'Pais', u'http://oglobo.globo.com/rss/plantaopais.xml')
              ,(u'Rio', u'http://oglobo.globo.com/rss/plantaorio.xml')
              ,(u'Saude', u'http://oglobo.globo.com/rss/plantaosaude.xml')
              ,(u'Viver Melhor', u'http://oglobo.globo.com/rss/plantaovivermelhor.xml')
              ,(u'Economia', u'http://oglobo.globo.com/rss/plantaoeconomia.xml')
              ,(u'Tecnologia', u'http://oglobo.globo.com/rss/plantaotecnologia.xml')
            ]

    def preprocess_html(self, soup):
        for item in soup.findAll(style=True):
            del item['style']
        return soup

    language = _('Portugese')