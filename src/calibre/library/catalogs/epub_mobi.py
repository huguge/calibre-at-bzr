#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from collections import namedtuple

from calibre import strftime
from calibre.customize import CatalogPlugin
from calibre.customize.conversion import OptionRecommendation, DummyReporter

Option = namedtuple('Option', 'option, default, dest, action, help')

class EPUB_MOBI(CatalogPlugin):
    'ePub catalog generator'

    name = 'Catalog_EPUB_MOBI'
    description = 'EPUB/MOBI catalog generator'
    supported_platforms = ['windows', 'osx', 'linux']
    minimum_calibre_version = (0, 7, 40)
    author = 'Greg Riker'
    version = (1, 0, 0)
    file_types = set(['epub','mobi'])

    THUMB_SMALLEST = "1.0"
    THUMB_LARGEST = "2.0"

    cli_options = [Option('--catalog-title', # {{{
                          default = 'My Books',
                          dest = 'catalog_title',
                          action = None,
                          help = _('Title of generated catalog used as title in metadata.\n'
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--debug-pipeline',
                           default=None,
                           dest='debug_pipeline',
                           action = None,
                           help=_("Save the output from different stages of the conversion "
                           "pipeline to the specified "
                           "directory. Useful if you are unsure at which stage "
                           "of the conversion process a bug is occurring.\n"
                           "Default: '%default'\n"
                           "Applies to: ePub, MOBI output formats")),
                   Option('--exclude-book-marker',
                          default=':',
                          dest='exclude_book_marker',
                          action = None,
                          help=_("field:pattern specifying custom field/contents indicating book should be excluded.\n"
                          "Default: '%default'\n"
                          "Applies to ePub, MOBI output formats")),
                   Option('--exclude-genre',
                          default='\[.+\]',
                          dest='exclude_genre',
                          action = None,
                          help=_("Regex describing tags to exclude as genres.\n" "Default: '%default' excludes bracketed tags, e.g. '[<tag>]'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--exclude-tags',
                          default=('~,'+_('Catalog')),
                          dest='exclude_tags',
                          action = None,
                          help=_("Comma-separated list of tag words indicating book should be excluded from output. "
                              "For example: 'skip' will match 'skip this book' and 'Skip will like this'. "
                              "Default: '%default'\n"
                              "Applies to: ePub, MOBI output formats")),
                   Option('--generate-authors',
                          default=False,
                          dest='generate_authors',
                          action = 'store_true',
                          help=_("Include 'Authors' section in catalog.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--generate-descriptions',
                          default=False,
                          dest='generate_descriptions',
                          action = 'store_true',
                          help=_("Include 'Descriptions' section in catalog.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--generate-genres',
                          default=False,
                          dest='generate_genres',
                          action = 'store_true',
                          help=_("Include 'Genres' section in catalog.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--generate-titles',
                          default=False,
                          dest='generate_titles',
                          action = 'store_true',
                          help=_("Include 'Titles' section in catalog.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--generate-series',
                          default=False,
                          dest='generate_series',
                          action = 'store_true',
                          help=_("Include 'Series' section in catalog.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--generate-recently-added',
                          default=False,
                          dest='generate_recently_added',
                          action = 'store_true',
                          help=_("Include 'Recently Added' section in catalog.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--header-note-source-field',
                          default='',
                          dest='header_note_source_field',
                          action = None,
                          help=_("Custom field containing note text to insert in Description header.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--merge-comments',
                          default='::',
                          dest='merge_comments',
                          action = None,
                          help=_("<custom field>:[before|after]:[True|False] specifying:\n"
                          " <custom field> Custom field containing notes to merge with Comments\n"
                          " [before|after] Placement of notes with respect to Comments\n"
                          " [True|False] - A horizontal rule is inserted between notes and Comments\n"
                          "Default: '%default'\n"
                          "Applies to ePub, MOBI output formats")),
                   Option('--output-profile',
                          default=None,
                          dest='output_profile',
                          action = None,
                          help=_("Specifies the output profile.  In some cases, an output profile is required to optimize the catalog for the device.  For example, 'kindle' or 'kindle_dx' creates a structured Table of Contents with Sections and Articles.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--read-book-marker',
                          default='tag:+',
                          dest='read_book_marker',
                          action = None,
                          help=_("field:pattern indicating book has been read.\n" "Default: '%default'\n"
                          "Applies to ePub, MOBI output formats")),
                   Option('--thumb-width',
                          default='1.0',
                          dest='thumb_width',
                          action = None,
                          help=_("Size hint (in inches) for book covers in catalog.\n"
                          "Range: 1.0 - 2.0\n"
                          "Default: '%default'\n"
                          "Applies to ePub, MOBI output formats")),
                   Option('--wishlist-tag',
                          default='Wishlist',
                          dest='wishlist_tag',
                          action = None,
                          help=_("Tag indicating book to be displayed as wishlist item.\n" "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                          ]
    # }}}

    def run(self, path_to_output, opts, db, notification=DummyReporter()):
        from calibre.library.catalogs.epub_mobi_builder import CatalogBuilder
        from calibre.utils.logging import default_log as log

        opts.log = log
        opts.fmt = self.fmt = path_to_output.rpartition('.')[2]

        # Add local options
        opts.creator = '%s, %s %s, %s' % (strftime('%A'), strftime('%B'), strftime('%d').lstrip('0'), strftime('%Y'))
        opts.creator_sort_as = '%s %s' % ('calibre', strftime('%Y-%m-%d'))
        opts.connected_kindle = False

        # Finalize output_profile
        op = opts.output_profile
        if op is None:
            op = 'default'

        if opts.connected_device['name'] and 'kindle' in opts.connected_device['name'].lower():
            opts.connected_kindle = True
            if opts.connected_device['serial'] and \
               opts.connected_device['serial'][:4] in ['B004','B005']:
                op = "kindle_dx"
            else:
                op = "kindle"
        opts.descriptionClip = 380 if op.endswith('dx') or 'kindle' not in op else 100
        opts.authorClip = 100 if op.endswith('dx') or 'kindle' not in op else 60
        opts.output_profile = op

        opts.basename = "Catalog"
        opts.cli_environment = not hasattr(opts,'sync')

        # Hard-wired to always sort descriptions by author, with series after non-series
        opts.sort_descriptions_by_author = True

        build_log = []

        build_log.append(u"%s(): Generating %s %sin %s environment" %
            (self.name,self.fmt,'for %s ' % opts.output_profile if opts.output_profile else '',
             'CLI' if opts.cli_environment else 'GUI'))

        # If exclude_genre is blank, assume user wants all genre tags included
        if opts.exclude_genre.strip() == '':
            opts.exclude_genre = '\[^.\]'
            build_log.append(" converting empty exclude_genre to '\[^.\]'")

        if opts.connected_device['is_device_connected'] and \
           opts.connected_device['kind'] == 'device':
            if opts.connected_device['serial']:
                build_log.append(u" connected_device: '%s' #%s%s " % \
                    (opts.connected_device['name'],
                     opts.connected_device['serial'][0:4],
                     'x' * (len(opts.connected_device['serial']) - 4)))
                for storage in opts.connected_device['storage']:
                    if storage:
                        build_log.append(u"  mount point: %s" % storage)
            else:
                build_log.append(u" connected_device: '%s'" % opts.connected_device['name'])
                try:
                    for storage in opts.connected_device['storage']:
                        if storage:
                            build_log.append(u"  mount point: %s" % storage)
                except:
                    build_log.append(u"  (no mount points)")
        else:
            build_log.append(u" connected_device: '%s'" % opts.connected_device['name'])

        opts_dict = vars(opts)
        if opts_dict['ids']:
            build_log.append(" book count: %d" % len(opts_dict['ids']))

        sections_list = []
        if opts.generate_authors:
            sections_list.append('Authors')
        if opts.generate_titles:
            sections_list.append('Titles')
        if opts.generate_series:
            sections_list.append('Series')
        if opts.generate_genres:
            sections_list.append('Genres')
        if opts.generate_recently_added:
            sections_list.append('Recently Added')
        if opts.generate_descriptions:
            sections_list.append('Descriptions')

        if not sections_list:
            if opts.cli_environment:
                opts.log.warn('*** No Section switches specified, enabling all Sections ***')
                opts.generate_authors = True
                opts.generate_titles = True
                opts.generate_series = True
                opts.generate_genres = True
                opts.generate_recently_added = True
                opts.generate_descriptions = True
                sections_list = ['Authors','Titles','Series','Genres','Recently Added','Descriptions']
            else:
                opts.log.warn('\n*** No enabled Sections, terminating catalog generation ***')
                return ["No Included Sections","No enabled Sections.\nCheck E-book options tab\n'Included sections'\n"]
        if opts.fmt == 'mobi' and sections_list == ['Descriptions']:
                warning = _("\n*** Adding 'By Authors' Section required for MOBI output ***")
                opts.log.warn(warning)
                sections_list.insert(0,'Authors')
                opts.generate_authors = True

        opts.log(u" Sections: %s" % ', '.join(sections_list))
        opts.section_list = sections_list

        # Limit thumb_width to 1.0" - 2.0"
        try:
            if float(opts.thumb_width) < float(self.THUMB_SMALLEST):
                log.warning("coercing thumb_width from '%s' to '%s'" % (opts.thumb_width,self.THUMB_SMALLEST))
                opts.thumb_width = self.THUMB_SMALLEST
            if float(opts.thumb_width) > float(self.THUMB_LARGEST):
                log.warning("coercing thumb_width from '%s' to '%s'" % (opts.thumb_width,self.THUMB_LARGEST))
                opts.thumb_width = self.THUMB_LARGEST
            opts.thumb_width = "%.2f" % float(opts.thumb_width)
        except:
            log.error("coercing thumb_width from '%s' to '%s'" % (opts.thumb_width,self.THUMB_SMALLEST))
            opts.thumb_width = "1.0"


        # Display opts
        keys = opts_dict.keys()
        keys.sort()
        build_log.append(" opts:")
        for key in keys:
            if key in ['catalog_title','authorClip','connected_kindle','descriptionClip',
                       'exclude_book_marker','exclude_genre','exclude_tags',
                       'header_note_source_field','merge_comments',
                       'output_profile','read_book_marker',
                       'search_text','sort_by','sort_descriptions_by_author','sync',
                       'thumb_width','wishlist_tag']:
                build_log.append("  %s: %s" % (key, repr(opts_dict[key])))

        if opts.verbose:
            log('\n'.join(line for line in build_log))

        self.opts = opts

        # Launch the Catalog builder
        catalog = CatalogBuilder(db, opts, self, report_progress=notification)

        if opts.verbose:
            log.info(" Begin catalog source generation")
        catalog.createDirectoryStructure()
        catalog.copyResources()
        catalog.calculateThumbnailSize()
        catalog_source_built = catalog.buildSources()

        if opts.verbose:
            if catalog_source_built:
                log.info(" Completed catalog source generation\n")
            else:
                log.error(" *** Terminated catalog generation, check log for details ***")

        if catalog_source_built:
            recommendations = []
            recommendations.append(('remove_fake_margins', False,
                OptionRecommendation.HIGH))
            recommendations.append(('comments', '', OptionRecommendation.HIGH))

            # Use to debug generated catalog code before conversion
            #setattr(opts,'debug_pipeline',os.path.expanduser("~/Desktop/Catalog debug"))

            dp = getattr(opts, 'debug_pipeline', None)
            if dp is not None:
                recommendations.append(('debug_pipeline', dp,
                    OptionRecommendation.HIGH))

            if opts.fmt == 'mobi' and opts.output_profile and opts.output_profile.startswith("kindle"):
                recommendations.append(('output_profile', opts.output_profile,
                    OptionRecommendation.HIGH))
                recommendations.append(('no_inline_toc', True,
                    OptionRecommendation.HIGH))
                recommendations.append(('book_producer',opts.output_profile,
                    OptionRecommendation.HIGH))

            # If cover exists, use it
            cpath = None
            try:
                search_text = 'title:"%s" author:%s' % (
                        opts.catalog_title.replace('"', '\\"'), 'calibre')
                matches = db.search(search_text, return_matches=True)
                if matches:
                    cpath = db.cover(matches[0], index_is_id=True, as_path=True)
                    if cpath and os.path.exists(cpath):
                        recommendations.append(('cover', cpath,
                            OptionRecommendation.HIGH))
            except:
                pass

            # Run ebook-convert
            from calibre.ebooks.conversion.plumber import Plumber
            plumber = Plumber(os.path.join(catalog.catalogPath,
                            opts.basename + '.opf'), path_to_output, log, report_progress=notification,
                            abort_after_input_dump=False)
            plumber.merge_ui_recommendations(recommendations)
            plumber.run()

            try:
                os.remove(cpath)
            except:
                pass

        # returns to gui2.actions.catalog:catalog_generated()
        return catalog.error

