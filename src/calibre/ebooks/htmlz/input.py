# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from calibre import guess_type
from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.metadata.opf2 import OPF
from calibre.utils.zipfile import ZipFile

class HTMLZInput(InputFormatPlugin):

    name        = 'HTLZ Input'
    author      = 'John Schember'
    description = 'Convert HTML files to HTML'
    file_types  = set(['htmlz'])

    def convert(self, stream, options, file_ext, log,
                accelerators):
        self.log = log
        html = u''
        top_levels = []

        # Extract content from zip archive.
        zf = ZipFile(stream)
        zf.extractall()

        # Find the HTML file in the archive. It needs to be
        # top level.
        index = u''
        multiple_html = False
        # Get a list of all top level files in the archive.
        for x in os.listdir('.'):
            if os.path.isfile(x):
                top_levels.append(x)
        # Try to find an index. file.
        for x in top_levels:
            if x.lower() in ('index.html', 'index.xhtml', 'index.htm'):
                index = x
                break
        # Look for multiple HTML files in the archive. We look at the
        # top level files only as only they matter in HTMLZ.
        for x in top_levels:
            if os.path.splitext(x)[1].lower() in ('.html', '.xhtml', '.htm'):
                # Set index to the first HTML file found if it's not
                # called index.
                if not index:
                    index = x
                else:
                    multiple_html = True
        # Warn the user if there multiple HTML file in the archive. HTMLZ
        # supports a single HTML file. A conversion with a multiple HTML file
        # HTMLZ archive probably won't turn out as the user expects. With
        # Multiple HTML files ZIP input should be used in place of HTMLZ.
        if multiple_html:
            log.warn(_('Multiple HTML files found in the archive. Only %s will be used.') % index)

        if index:
            with open(index, 'rb') as tf:
                html = tf.read()
        else:
            raise Exception(_('No top level HTML file found.'))

        if not html:
            raise Exception(_('Top level HTML file %s is empty') % index)

        # Encoding
        if options.input_encoding:
            ienc = options.input_encoding
        else:
            ienc = xml_to_unicode(html[:4096])[-1]
        html = html.decode(ienc, 'replace')

        # Run the HTML through the html processing plugin.
        from calibre.customize.ui import plugin_for_input_format
        html_input = plugin_for_input_format('html')
        for opt in html_input.options:
            setattr(options, opt.option.name, opt.recommended_value)
        options.input_encoding = 'utf-8'
        base = os.getcwdu()
        fname = os.path.join(base, 'index.html')
        c = 0
        while os.path.exists(fname):
            c += 1
            fname = 'index%d.html'%c
        htmlfile = open(fname, 'wb')
        with htmlfile:
            htmlfile.write(html.encode('utf-8'))
        odi = options.debug_pipeline
        options.debug_pipeline = None
        # Generate oeb from html conversion.
        oeb = html_input.convert(open(htmlfile.name, 'rb'), options, 'html', log,
                {})
        options.debug_pipeline = odi
        os.remove(htmlfile.name)

        # Set metadata from file.
        from calibre.customize.ui import get_file_type_metadata
        from calibre.ebooks.oeb.transforms.metadata import meta_info_to_oeb_metadata
        mi = get_file_type_metadata(stream, file_ext)
        meta_info_to_oeb_metadata(mi, oeb.metadata, log)

        # Get the cover path from the OPF.
        cover_path = None
        opf = None
        for x in top_levels:
            if os.path.splitext(x)[1].lower() in ('.opf'):
                opf = x
                break
        if opf:
            opf = OPF(opf, basedir=os.getcwd())
            cover_path = opf.raster_cover
        # Set the cover.
        if cover_path:
            cdata = None
            with open(os.path.join(os.getcwd(), cover_path), 'rb') as cf:
                cdata = cf.read()
            cover_name = os.path.basename(cover_path)
            id, href = oeb.manifest.generate('cover', cover_name)
            oeb.manifest.add(id, href, guess_type(cover_name)[0], data=cdata)
            oeb.guide.add('cover', 'Cover', href)

        return oeb
