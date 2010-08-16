# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.pdb_input_ui import Ui_Form
from calibre.gui2.convert import Widget

class PluginWidget(Widget, Ui_Form):

    TITLE = _('PDB Input')
    HELP = _('Options specific to')+' PDB '+_('input')
    COMMIT_NAME = 'pdb_input'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
            ['single_line_paras', 'print_formatted_paras'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
