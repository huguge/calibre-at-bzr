#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2009, Darko Miletic <darko.miletic at gmail.com>'
'''
lacuarta.cl
'''

from calibre.web.feeds.news import BasicNewsRecipe

class LaCuarta(BasicNewsRecipe):
    title                 = 'La Cuarta'
    __author__            = 'Darko Miletic'
    description           = 'La Cuarta Cibernetica: El Diario popular'
    publisher             = 'CODISA, Consorcio Digital S.A.'
    category              = 'news, politics, entertainment, Chile'
    oldest_article        = 2
    max_articles_per_feed = 100
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'cp1252'
    remove_javascript     = True
    
    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 
                        
    keep_only_tags = [dict(name='div', attrs={'class':'articulo desplegado'}) ]

    remove_tags = [  
                     dict(name='ul')
                    ,dict(name='div', attrs={'id':['toolbox','articleImageDisplayer','enviarAmigo']})
                    ,dict(name='div', attrs={'class':['par ad-1','par ad-2']})
                    ,dict(name='input')
                    ,dict(name='p', attrs={'id':['mensajeError','mensajeEnviandoNoticia','mensajeExito']})
                    ,dict(name='strong', text='PUBLICIDAD')
                  ]

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Language" content="es-CL"/>'
        soup.head.insert(0,mtag)    
        for item in soup.findAll(style=True):
            del item['style']
        return soup
    
    feeds = [(u'Noticias', u'http://lacuarta.cl/app/rss?sc=TEFDVUFSVEE=')]

    
    language = _('Spanish')