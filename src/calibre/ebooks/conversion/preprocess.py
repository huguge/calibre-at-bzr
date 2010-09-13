#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import functools, re

from calibre import entity_to_unicode

XMLDECL_RE    = re.compile(r'^\s*<[?]xml.*?[?]>')
SVG_NS       = 'http://www.w3.org/2000/svg'
XLINK_NS     = 'http://www.w3.org/1999/xlink'

convert_entities = functools.partial(entity_to_unicode,
        result_exceptions = {
            u'<' : '&lt;',
            u'>' : '&gt;',
            u"'" : '&apos;',
            u'"' : '&quot;',
            u'&' : '&amp;',
        })
_span_pat = re.compile('<span.*?</span>', re.DOTALL|re.IGNORECASE)

LIGATURES = {
#        u'\u00c6': u'AE',
#        u'\u00e6': u'ae',
#        u'\u0152': u'OE',
#        u'\u0153': u'oe',
#        u'\u0132': u'IJ',
#        u'\u0133': u'ij',
#        u'\u1D6B': u'ue',
        u'\uFB00': u'ff',
        u'\uFB01': u'fi',
        u'\uFB02': u'fl',
        u'\uFB03': u'ffi',
        u'\uFB04': u'ffl',
        u'\uFB05': u'ft',
        u'\uFB06': u'st',
        }

_ligpat = re.compile(u'|'.join(LIGATURES))

def sanitize_head(match):
    x = match.group(1)
    x = _span_pat.sub('', x)
    return '<head>\n%s\n</head>' % x

def chap_head(match):
    chap = match.group('chap')
    title = match.group('title')
    if not title:
               return '<h1>'+chap+'</h1><br/>\n'
    else:
               return '<h1>'+chap+'</h1>\n<h3>'+title+'</h3>\n'

def wrap_lines(match):
    ital = match.group('ital')
    if not ital:
               return ' '
    else:
               return ital+' '

def line_length(format, raw, percent):
    '''
    raw is the raw text to find the line length to use for wrapping.
    percentage is a decimal number, 0 - 1 which is used to determine
    how far in the list of line lengths to use. The list of line lengths is
    ordered smallest to larged and does not include duplicates. 0.5 is the
    median value.
    '''
    raw = raw.replace('&nbsp;', ' ')
    if format == 'html':
        linere = re.compile('(?<=<p).*?(?=</p>)', re.DOTALL)
    elif format == 'pdf':
        linere = re.compile('(?<=<br>).*?(?=<br>)', re.DOTALL)
    elif format == 'spanned_html':
        linere = re.compile('(?<=<span).*?(?=</span>)', re.DOTALL)
    lines = linere.findall(raw)

    lengths = []
    for line in lines:
        if len(line) > 0:
            lengths.append(len(line))

    if not lengths:
        return 0

    lengths = list(set(lengths))
    total = sum(lengths)
    avg = total / len(lengths)
    max_line = avg * 2

    lengths = sorted(lengths)
    for i in range(len(lengths) - 1, -1, -1):
        if lengths[i] > max_line:
            del lengths[i]

    if percent > 1:
        percent = 1
    if percent < 0:
        percent = 0

    index = int(len(lengths) * percent) - 1

    return lengths[index]


class CSSPreProcessor(object):

    PAGE_PAT   = re.compile(r'@page[^{]*?{[^}]*?}')

    def __call__(self, data, add_namespace=False):
        from calibre.ebooks.oeb.base import XHTML_CSS_NAMESPACE
        data = self.PAGE_PAT.sub('', data)
        if not add_namespace:
            return data
        ans, namespaced = [], False
        for line in data.splitlines():
            ll = line.lstrip()
            if not (namespaced or ll.startswith('@import') or
                        ll.startswith('@charset')):
                ans.append(XHTML_CSS_NAMESPACE.strip())
                namespaced = True
            ans.append(line)

        return u'\n'.join(ans)

class HTMLPreProcessor(object):

    PREPROCESS = [
                  # Some idiotic HTML generators (Frontpage I'm looking at you)
                  # Put all sorts of crap into <head>. This messes up lxml
                  (re.compile(r'<head[^>]*>\n*(.*?)\n*</head>', re.IGNORECASE|re.DOTALL),
                   sanitize_head),
                  # Convert all entities, since lxml doesn't handle them well
                  (re.compile(r'&(\S+?);'), convert_entities),
                  # Remove the <![if/endif tags inserted by everybody's darling, MS Word
                  (re.compile(r'</{0,1}!\[(end){0,1}if\]{0,1}>', re.IGNORECASE),
                   lambda match: ''),
                  ]

    # Fix pdftohtml markup
    PDFTOHTML  = [
                  # Fix umlauts
                  # ¨
                  (re.compile(u'¨\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'ä'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Ä'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'ë'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'Ë'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'ï'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Ï'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ö'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ö'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'ü'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Ü'),

                  # Fix accents
                  # `
                  (re.compile(u'`\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'à'),
                  (re.compile(u'`\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'À'),
                  (re.compile(u'`\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'è'),
                  (re.compile(u'`\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'È'),
                  (re.compile(u'`\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'ì'),
                  (re.compile(u'`\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Ì'),
                  (re.compile(u'`\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ò'),
                  (re.compile(u'`\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ò'),
                  (re.compile(u'`\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'ù'),
                  (re.compile(u'`\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Ù'),
                  # ` with letter before
                  (re.compile(u'a\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'à'),
                  (re.compile(u'A\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'À'),
                  (re.compile(u'e\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'è'),
                  (re.compile(u'E\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'È'),
                  (re.compile(u'i\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'ì'),
                  (re.compile(u'I\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'Ì'),
                  (re.compile(u'o\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'ò'),
                  (re.compile(u'O\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'Ò'),
                  (re.compile(u'u\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'ù'),
                  (re.compile(u'U\s*(<br.*?>)*\s*`', re.UNICODE), lambda match: u'Ù'),

                  # ´
                  (re.compile(u'´\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'á'),
                  (re.compile(u'´\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Á'),
                  (re.compile(u'´\s*(<br.*?>)*\s*c', re.UNICODE), lambda match: u'ć'),
                  (re.compile(u'´\s*(<br.*?>)*\s*C', re.UNICODE), lambda match: u'Ć'),
                  (re.compile(u'´\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'é'),
                  (re.compile(u'´\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'É'),
                  (re.compile(u'´\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'í'),
                  (re.compile(u'´\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Í'),
                  (re.compile(u'´\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ó'),
                  (re.compile(u'´\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ó'),
                  (re.compile(u'´\s*(<br.*?>)*\s*n', re.UNICODE), lambda match: u'ń'),
                  (re.compile(u'´\s*(<br.*?>)*\s*N', re.UNICODE), lambda match: u'Ń'),
                  (re.compile(u'´\s*(<br.*?>)*\s*s', re.UNICODE), lambda match: u'ś'),
                  (re.compile(u'´\s*(<br.*?>)*\s*S', re.UNICODE), lambda match: u'Ś'),
                  (re.compile(u'´\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'ú'),
                  (re.compile(u'´\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Ú'),
                  (re.compile(u'´\s*(<br.*?>)*\s*z', re.UNICODE), lambda match: u'ź'),
                  (re.compile(u'´\s*(<br.*?>)*\s*Z', re.UNICODE), lambda match: u'Ź'),

                  # ˆ
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'â'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Â'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'ê'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'Ê'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'î'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Î'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ô'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ô'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'û'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Û'),

                  # ¸
                  (re.compile(u'¸\s*(<br.*?>)*\s*c', re.UNICODE), lambda match: u'ç'),
                  (re.compile(u'¸\s*(<br.*?>)*\s*C', re.UNICODE), lambda match: u'Ç'),

                  # ˛
                  (re.compile(u'˛\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'ą'),
                  (re.compile(u'˛\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Ą'),
                  (re.compile(u'˛\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'ę'),
                  (re.compile(u'˛\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'Ę'),
                  
                  # ˙
                  (re.compile(u'˙\s*(<br.*?>)*\s*z', re.UNICODE), lambda match: u'ż'),
                  (re.compile(u'˙\s*(<br.*?>)*\s*Z', re.UNICODE), lambda match: u'Ż'),

                  # If pdf printed from a browser then the header/footer has a reliable pattern
                  (re.compile(r'((?<=</a>)\s*file:////?[A-Z].*<br>|file:////?[A-Z].*<br>(?=\s*<hr>))', re.IGNORECASE), lambda match: ''),

                  # Center separator lines
                  (re.compile(u'<br>\s*(?P<break>([*#•]+\s*)+)\s*<br>'), lambda match: '<p>\n<p style="text-align:center">' + match.group(1) + '</p>'),

                  # Remove page links
                  (re.compile(r'<a name=\d+></a>', re.IGNORECASE), lambda match: ''),
                  # Remove <hr> tags
                  (re.compile(r'<hr.*?>', re.IGNORECASE), lambda match: '<br>'),

                  # Remove gray background
                  (re.compile(r'<BODY[^<>]+>'), lambda match : '<BODY>'),

                  # Detect Chapters to match default XPATH in GUI
                  (re.compile(r'<br>\s*(?P<chap>(<[ibu]>){0,2}\s*.?(Introduction|Chapter|Epilogue|Prologue|Book|Part|Dedication|Volume|Preface|Acknowledgments)\s*([\d\w-]+\s*){0,3}\s*(</[ibu]>){0,2})\s*(<br>\s*){1,3}\s*(?P<title>(<[ibu]>){0,2}(\s*\w+){1,4}\s*(</[ibu]>){0,2}\s*<br>)?', re.IGNORECASE), chap_head),
                  # Cover the case where every letter in a chapter title is separated by a space
                  (re.compile(r'<br>\s*(?P<chap>([A-Z]\s+){4,}\s*([\d\w-]+\s*){0,3}\s*)\s*(<br>\s*){1,3}\s*(?P<title>(<[ibu]>){0,2}(\s*\w+){1,4}\s*(</[ibu]>){0,2}\s*(<br>))?'), chap_head),
                  
                  # Have paragraphs show better
                  (re.compile(r'<br.*?>'), lambda match : '<p>'),
                  # Clean up spaces
                  (re.compile(u'(?<=[\.,;\?!”"\'])[\s^ ]*(?=<)'), lambda match: ' '),
                  # Add space before and after italics
                  (re.compile(u'(?<!“)<i>'), lambda match: ' <i>'),
                  (re.compile(r'</i>(?=\w)'), lambda match: '</i> '),                            
                 ]

    # Fix Book Designer markup
    BOOK_DESIGNER = [
                     # HR
                     (re.compile('<hr>', re.IGNORECASE),
                      lambda match : '<span style="page-break-after:always"> </span>'),
                     # Create header tags
                     (re.compile('<h2[^><]*?id=BookTitle[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h1 id="BookTitle" align="%s">%s</h1>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile('<h2[^><]*?id=BookAuthor[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h2 id="BookAuthor" align="%s">%s</h2>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile('<span[^><]*?id=title[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h2 class="title">%s</h2>'%(match.group(1),)),
                     (re.compile('<span[^><]*?id=subtitle[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h3 class="subtitle">%s</h3>'%(match.group(1),)),
                     ]
    def __init__(self, input_plugin_preprocess, plugin_preprocess,
            extra_opts=None):
        self.input_plugin_preprocess = input_plugin_preprocess
        self.plugin_preprocess = plugin_preprocess
        self.extra_opts = extra_opts

    def is_baen(self, src):
        return re.compile(r'<meta\s+name="Publisher"\s+content=".*?Baen.*?"',
                          re.IGNORECASE).search(src) is not None

    def is_book_designer(self, raw):
        return re.search('<H2[^><]*id=BookTitle', raw) is not None

    def is_pdftohtml(self, src):
        return '<!-- created by calibre\'s pdftohtml -->' in src[:1000]

    def __call__(self, html, remove_special_chars=None,
            get_preprocess_html=False):
        if remove_special_chars is not None:
            html = remove_special_chars.sub('', html)
        html = html.replace('\0', '')
        is_pdftohtml = self.is_pdftohtml(html)
        if self.is_baen(html):
            rules = []
        elif self.is_book_designer(html):
            rules = self.BOOK_DESIGNER
        elif is_pdftohtml:
            rules = self.PDFTOHTML
        else:
            rules = []

        start_rules = []
        if is_pdftohtml:
            # Remove non breaking spaces
            start_rules.append((re.compile(ur'\u00a0'), lambda match : ' '))

        if not getattr(self.extra_opts, 'keep_ligatures', False):
            html = _ligpat.sub(lambda m:LIGATURES[m.group()], html)

        end_rules = []
        if getattr(self.extra_opts, 'remove_header', None):
            try:
                rules.insert(0,
                    (re.compile(self.extra_opts.header_regex), lambda match : '')
                )
            except:
                import traceback
                print 'Failed to parse remove_header regexp'
                traceback.print_exc()

        if getattr(self.extra_opts, 'remove_footer', None):
            try:
                rules.insert(0,
                    (re.compile(self.extra_opts.footer_regex), lambda match : '')
                )
            except:
                import traceback
                print 'Failed to parse remove_footer regexp'
                traceback.print_exc()
      
        # unwrap hyphenation - moved here so it's executed after header/footer removal
        if is_pdftohtml:
            # unwrap visible dashes and hyphens - don't delete they are often hyphens for
            # for compound words, formatting, etc
            end_rules.append((re.compile(u'(?<=[-–—])\s*<p>\s*(?=[[a-z\d])'), lambda match: ''))
            # unwrap/delete soft hyphens
            end_rules.append((re.compile(u'[­](\s*<p>)+\s*(?=[[a-z\d])'), lambda match: ''))
            # unwrap/delete soft hyphens with formatting
            end_rules.append((re.compile(u'[­]\s*(</(i|u|b)>)+(\s*<p>)+\s*(<(i|u|b)>)+\s*(?=[[a-z\d])'), lambda match: ''))
        
        # Make the more aggressive chapter marking regex optional with the preprocess option to 
        # reduce false positives and move after header/footer removal
        if getattr(self.extra_opts, 'preprocess_html', None):
            if is_pdftohtml:
                end_rules.append((re.compile(r'<p>\s*(?P<chap>(<[ibu]>){0,2}\s*([A-Z \'"!]{3,})\s*([\dA-Z:]+\s){0,4}\s*(</[ibu]>){0,2})\s*<p>\s*(?P<title>(<[ibu]>){0,2}(\s*\w+){1,4}\s*(</[ibu]>){0,2}\s*<p>)?'), chap_head),)
                
        if getattr(self.extra_opts, 'unwrap_factor', 0.0) > 0.01:
            length = line_length('pdf', html, getattr(self.extra_opts, 'unwrap_factor'))
            if length:
                # print "The pdf line length returned is " + str(length)
                end_rules.append(
                    # Un wrap using punctuation
                    (re.compile(r'(?<=.{%i}[a-z,;:)\-IA])\s*(?P<ital></(i|b|u)>)?\s*(<p.*?>\s*)+\s*(?=(<(i|b|u)>)?\s*[\w\d$(])' % length, re.UNICODE), wrap_lines),
                )

        for rule in self.PREPROCESS + start_rules:
            html = rule[0].sub(rule[1], html)

        if get_preprocess_html:
            return html

        def dump(raw, where):
            import os
            dp = getattr(self.extra_opts, 'debug_pipeline', None)
            if dp and os.path.exists(dp):
                odir = os.path.join(dp, 'input')
                if os.path.exists(odir):
                    odir = os.path.join(odir, where)
                    if not os.path.exists(odir):
                        os.makedirs(odir)
                    name, i = None, 0
                    while not name or os.path.exists(os.path.join(odir, name)):
                        i += 1
                        name = '%04d.html'%i
                    with open(os.path.join(odir, name), 'wb') as f:
                        f.write(raw.encode('utf-8'))

        #dump(html, 'pre-preprocess')

        for rule in rules + end_rules:
            html = rule[0].sub(rule[1], html)

        #dump(html, 'post-preprocess')

        # Handle broken XHTML w/ SVG (ugh)
        if 'svg:' in html and SVG_NS not in html:
            html = html.replace(
                '<html', '<html xmlns:svg="%s"' % SVG_NS, 1)
        if 'xlink:' in html and XLINK_NS not in html:
            html = html.replace(
                '<html', '<html xmlns:xlink="%s"' % XLINK_NS, 1)

        html = XMLDECL_RE.sub('', html)

        if getattr(self.extra_opts, 'asciiize', False):
            from calibre.ebooks.unidecode.unidecoder import Unidecoder
            unidecoder = Unidecoder()
            html = unidecoder.decode(html)

        if self.plugin_preprocess:
            html = self.input_plugin_preprocess(html)

        return html

