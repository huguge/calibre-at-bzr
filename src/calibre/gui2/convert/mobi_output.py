#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import Qt

from calibre.gui2.convert.mobi_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.gui2.widgets import FontFamilyModel
from calibre.utils.fonts import fontconfig

font_family_model = None

class PluginWidget(Widget, Ui_Form):

    TITLE = _('MOBI Output')
    HELP = _('Options specific to')+' MOBI '+_('output')


    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, 'mobi_output',
                ['prefer_author_sort', 'rescale_images', 'toc_title',
                'dont_compress', 'no_inline_toc', 'masthead_font','personal_doc']
                )
        self.db, self.book_id = db, book_id

        global font_family_model
        if font_family_model is None:
            font_family_model = FontFamilyModel()
            try:
                font_family_model.families = fontconfig.find_font_families(allowed_extensions=['ttf'])
            except:
                import traceback
                font_family_model.families = []
                print 'WARNING: Could not load fonts'
                traceback.print_exc()
            font_family_model.families.sort()
            font_family_model.families[:0] = [_('Default')]

        self.font_family_model = font_family_model
        self.opt_masthead_font.setModel(self.font_family_model)

        self.initialize_options(get_option, get_help, db, book_id)

    def set_value_handler(self, g, val):
        if unicode(g.objectName()) in 'opt_masthead_font':
            idx = -1
            if val:
                idx = g.findText(val, Qt.MatchFixedString)
            if idx < 0:
                idx = 0
            g.setCurrentIndex(idx)
            return True
        return False
