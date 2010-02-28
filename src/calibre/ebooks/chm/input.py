''' CHM File decoding support '''
__license__ = 'GPL v3'
__copyright__  = '2008, Kovid Goyal <kovid at kovidgoyal.net>,' \
                 ' and Alex Bramley <a.bramley at gmail.com>.'

import os, uuid

from lxml import html

from calibre.customize.conversion import InputFormatPlugin
from calibre.ebooks.chm.reader import CHMReader, match_string
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.localization import get_lang
from calibre.utils.filenames import ascii_filename

class CHMInput(InputFormatPlugin):

    name        = 'CHM Input'
    author      = 'Kovid Goyal and Alex Bramley'
    description = 'Convert CHM files to OEB'
    file_types  = set(['chm'])

    def _chmtohtml(self, output_dir, chm_path, no_images, log):
        log.debug('Opening CHM file')
        rdr = CHMReader(chm_path, log)
        log.debug('Extracting CHM to %s' % output_dir)
        rdr.extract_content(output_dir)
        return rdr.hhc_path


    def convert(self, stream, options, file_ext, log, accelerators):
        from calibre.ebooks.metadata.chm import get_metadata_
        from calibre.customize.ui import plugin_for_input_format

        log.debug('Processing CHM...')
        with TemporaryDirectory('chm2oeb') as tdir:
            html_input = plugin_for_input_format('html')
            for opt in html_input.options:
                setattr(options, opt.option.name, opt.recommended_value)
            options.input_encoding = 'utf-8'
            no_images = False #options.no_images
            chm_name = stream.name
            #chm_data = stream.read()

            #closing stream so CHM can be opened by external library
            stream.close()
            log.debug('tdir=%s' % tdir)
            log.debug('stream.name=%s' % stream.name)
            mainname = self._chmtohtml(tdir, chm_name, no_images, log)
            mainpath = os.path.join(tdir, mainname)

            metadata = get_metadata_(tdir)

            odi = options.debug_pipeline
            options.debug_pipeline = None
            # try a custom conversion:
            #oeb = self._create_oebbook(mainpath, tdir, options, log, metadata)
            # try using html converter:
            htmlpath = self._create_html_root(mainpath, log)
            oeb = self._create_oebbook_html(htmlpath, tdir, options, log, metadata)
            options.debug_pipeline = odi
            #log.debug('DEBUG: Not removing tempdir %s' % tdir)
        return oeb

    def _create_oebbook_html(self, htmlpath, basedir, opts, log, mi):
        # use HTMLInput plugin to generate book
        from calibre.ebooks.html.input import HTMLInput
        opts.breadth_first = True
        htmlinput = HTMLInput(None)
        oeb = htmlinput.create_oebbook(htmlpath, basedir, opts, log, mi)
        return oeb


    def _create_oebbook(self, hhcpath, basedir, opts, log, mi):
        from calibre.ebooks.conversion.plumber import create_oebbook
        from calibre.ebooks.oeb.base import DirContainer
        oeb = create_oebbook(log, None, opts, self,
                encoding=opts.input_encoding, populate=False)
        self.oeb = oeb

        metadata = oeb.metadata
        if mi.title:
            metadata.add('title', mi.title)
        if mi.authors:
            for a in mi.authors:
                metadata.add('creator', a, attrib={'role':'aut'})
        if mi.publisher:
            metadata.add('publisher', mi.publisher)
        if mi.isbn:
            metadata.add('identifier', mi.isbn, attrib={'scheme':'ISBN'})
        if not metadata.language:
            oeb.logger.warn(u'Language not specified')
            metadata.add('language', get_lang())
        if not metadata.creator:
            oeb.logger.warn('Creator not specified')
            metadata.add('creator', _('Unknown'))
        if not metadata.title:
            oeb.logger.warn('Title not specified')
            metadata.add('title', _('Unknown'))

        bookid = str(uuid.uuid4())
        metadata.add('identifier', bookid, id='uuid_id', scheme='uuid')
        for ident in metadata.identifier:
            if 'id' in ident.attrib:
                self.oeb.uid = metadata.identifier[0]
                break

        hhcdata = self._read_file(hhcpath)
        hhcroot = html.fromstring(hhcdata)
        chapters = self._process_nodes(hhcroot)
        #print "============================="
        #print "Printing hhcroot"
        #print etree.tostring(hhcroot, pretty_print=True)
        #print "============================="
        log.debug('Found %d section nodes' % len(chapters))

        if len(chapters) > 0:
            path0 = chapters[0][1]
            subpath = os.path.dirname(path0)
            htmlpath = os.path.join(basedir, subpath)

            oeb.container = DirContainer(htmlpath, log)
            for chapter in chapters:
                title = chapter[0]
                basename = os.path.basename(chapter[1])
                self._add_item(oeb, title, basename)

            oeb.container = DirContainer(htmlpath, oeb.log)
        return oeb

    def _create_html_root(self, hhcpath, log):
        hhcdata = self._read_file(hhcpath)
        hhcroot = html.fromstring(hhcdata)
        chapters = self._process_nodes(hhcroot)
        #print "============================="
        #print "Printing hhcroot"
        #print etree.tostring(hhcroot, pretty_print=True)
        #print "============================="
        log.debug('Found %d section nodes' % len(chapters))
        htmlpath = os.path.splitext(hhcpath)[0] + ".html"
        f = open(htmlpath, 'wb')
        f.write("<HTML><HEAD></HEAD><BODY>\r\n")

        if chapters:
            path0 = chapters[0][1]
            subpath = os.path.dirname(path0)

            for chapter in chapters:
                title = chapter[0]
                rsrcname = os.path.basename(chapter[1])
                rsrcpath = os.path.join(subpath, rsrcname)
                # title should already be url encoded
                url = "<br /><a href=" + rsrcpath + ">" + title + " </a>\r\n"
                f.write(url)

        f.write("</BODY></HTML>")
        f.close()
        return htmlpath


    def _read_file(self, name):
        f = open(name, 'rb')
        data = f.read()
        f.close()
        return data

    def _visit_node(self, node, chapters, depth):
        # check that node is a normal node (not a comment, DOCTYPE, etc.)
        # (normal nodes have string tags)
        if isinstance(node.tag, basestring):
            if match_string(node.tag, 'object') and match_string(node.attrib['type'], 'text/sitemap'):
                for child in node:
                    if match_string(child.tag,'param') and match_string(child.attrib['name'], 'name'):
                        chapter_title = child.attrib['value']
                    if match_string(child.tag,'param') and match_string(child.attrib['name'],'local'):
                        chapter_path = child.attrib['value']
                if chapter_title is not None and chapter_path is not None:
                    chapter = [chapter_title, chapter_path, depth]
                    chapters.append(chapter)
            if node.tag=="UL":
                depth = depth + 1
            if node.tag=="/UL":
                depth = depth - 1

    def _process_nodes(self, root):
        chapters = []
        depth = 0
        for node in root.iter():
            self._visit_node(node, chapters, depth)
        return chapters

    def _add_item(self, oeb, title, path):
        bname = os.path.basename(path)
        id, href = oeb.manifest.generate(id='html',
                href=ascii_filename(bname))
        item = oeb.manifest.add(id, href, 'text/html')
        item.html_input_href = bname
        oeb.spine.add(item, True)
        oeb.toc.add(title, item.href)

