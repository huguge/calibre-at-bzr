#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008-2009, Darko Miletic <darko.miletic at gmail.com>'
'''
elargentino.com
'''
from calibre.web.feeds.news import BasicNewsRecipe

class ElArgentino(BasicNewsRecipe):
    title                 = 'ElArgentino.com'
    __author__            = 'Darko Miletic'
    description           = 'Informacion Libre las 24 horas'
    publisher             = 'ElArgentino.com'
    category              = 'news, politics, Argentina'    
    oldest_article        = 2
    max_articles_per_feed = 100
    remove_javascript     = True
    no_stylesheets        = True
    use_embedded_content  = False
    encoding              = 'utf8'
    cover_url             = 'http://www.elargentino.com/TemplateWeb/MediosFooter/tapa_elargentino.png'
    language              = _('Spanish')

    html2lrf_options = [
                          '--comment', description
                        , '--category', category
                        , '--publisher', publisher
                        ]
    
    html2epub_options = 'publisher="' + publisher + '"\ncomments="' + description + '"\ntags="' + category + '"' 

    remove_tags = [
                     dict(name='div', attrs={'id':'noprint'              })
                    ,dict(name='div', attrs={'class':'encabezadoImprimir'})
                    ,dict(name='a'  , attrs={'target':'_blank'           })
                  ]
    
    feeds = [ 
              (u'Portada'     , u'http://www.elargentino.com/Highlights.aspx?Content-Type=text/xml&ChannelDesc=Home'                                             )
             ,(u'Pais'        , u'http://www.elargentino.com/Highlights.aspx?ParentType=Section&ParentId=112&Content-Type=text/xml&ChannelDesc=Pa%C3%ADs'        )
             ,(u'Economia'    , u'http://www.elargentino.com/Highlights.aspx?ParentType=Section&ParentId=107&Content-Type=text/xml&ChannelDesc=Econom%C3%ADa'    )
             ,(u'Mundo'       , u'http://www.elargentino.com/Highlights.aspx?ParentType=Section&ParentId=113&Content-Type=text/xml&ChannelDesc=Mundo'            )
             ,(u'Tecnologia'  , u'http://www.elargentino.com/Highlights.aspx?ParentType=Section&ParentId=118&Content-Type=text/xml&ChannelDesc=Tecnolog%C3%ADa'  )
             ,(u'Espectaculos', u'http://www.elargentino.com/Highlights.aspx?ParentType=Section&ParentId=114&Content-Type=text/xml&ChannelDesc=Espect%C3%A1culos')
             ,(u'Deportes'    , u'http://www.elargentino.com/Highlights.aspx?ParentType=Section&ParentId=106&Content-Type=text/xml&ChannelDesc=Deportes'         )
             ,(u'Sociedad'    , u'http://www.elargentino.com/Highlights.aspx?ParentType=Section&ParentId=109&Content-Type=text/xml&ChannelDesc=Sociedad'         )
             ,(u'Entrevistas' , u'http://www.elargentino.com/Highlights.aspx?ParentType=Section&ParentId=115&Content-Type=text/xml&ChannelDesc=Entrevistas'      )
            ]

    def print_version(self, url):
        main, sep, article_part = url.partition('/nota-')
        article_id, rsep, rrest = article_part.partition('-')    
        return u'http://www.elargentino.com/Impresion.aspx?Id=' + article_id

    def preprocess_html(self, soup):
        mtag = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n<meta http-equiv="Content-Language" content="es-AR"/>\n'
        soup.head.insert(0,mtag)
        for item in soup.findAll(style=True):
            del item['style']        
        return soup
