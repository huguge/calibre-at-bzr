#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.look_and_feel_ui import Ui_Form
from calibre.gui2.convert import Widget

class LookAndFeelWidget(Widget, Ui_Form):

    TITLE = _('Look & Feel')
    ICON  = ':/images/lookfeel.svg'
    HELP  = _('Control the look and feel of the output')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, 'look_and_feel',
                ['dont_justify', 'extra_css', 'base_font_size',
                    'font_size_mapping', 'insert_metadata', 'line_height',
                    'linearize_tables', 'remove_first_image',
                    'remove_paragraph_spacing']
                )
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)

