from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.customize.conversion import InputFormatPlugin

class MOBIInput(InputFormatPlugin):

    name        = 'MOBI Input'
    author      = 'Kovid Goyal'
    description = 'Convert MOBI files (.mobi, .prc, .azw) to HTML'
    file_types  = set(['mobi', 'prc', 'azw'])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.mobi.reader import MobiReader
        from lxml import html
        mr = MobiReader(stream, log, options.input_encoding,
                        options.debug_pipeline)
        parse_cache = {}
        mr.extract_content('.', parse_cache)
        raw = parse_cache.pop('calibre_raw_mobi_markup', False)
        if raw:
            if isinstance(raw, unicode):
                raw = raw.encode('utf-8')
            open('debug-raw.html', 'wb').write(raw)
        for f, root in parse_cache.items():
            with open(f, 'wb') as q:
                q.write(html.tostring(root, encoding='utf-8', method='xml',
                    include_meta_content_type=False))
                accelerators['pagebreaks'] = '//h:div[@class="mbp_pagebreak"]'
        return mr.created_opf_path
