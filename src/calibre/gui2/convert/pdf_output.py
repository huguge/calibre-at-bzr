# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.pdf_output_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.pdf.pageoptions import PAPER_SIZES, ORIENTATIONS
from calibre.gui2.widgets import BasicComboModel

paper_size_model = None
orientation_model = None

class PluginWidget(Widget, Ui_Form):

    TITLE = _('PDF Output')
    HELP = _('Options specific to')+' PDF '+_('output')
    COMMIT_NAME = 'pdf_output'
    ICON = I('mimetypes/pdf.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, ['paper_size',
            'orientation', 'preserve_cover_aspect_ratio'])
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)

        default_paper_size = self.opt_paper_size.currentText()
        default_orientation = self.opt_orientation.currentText()

        global paper_size_model
        if paper_size_model is None:
            paper_size_model = BasicComboModel(PAPER_SIZES.keys())
        self.paper_size_model = paper_size_model
        self.opt_paper_size.setModel(self.paper_size_model)

        default_paper_size_index = self.opt_paper_size.findText(default_paper_size)
        letter_index = self.opt_paper_size.findText('letter')
        self.opt_paper_size.setCurrentIndex(default_paper_size_index if default_paper_size_index != -1 else letter_index if letter_index != -1 else 0)

        global orientation_model
        if orientation_model is None:
            orientation_model = BasicComboModel(ORIENTATIONS.keys())
        self.orientation_model = orientation_model
        self.opt_orientation.setModel(self.orientation_model)

        default_orientation_index = self.opt_orientation.findText(default_orientation)
        orientation_index = self.opt_orientation.findText('portrait')
        self.opt_orientation.setCurrentIndex(default_orientation_index if default_orientation_index != -1 else orientation_index if orientation_index != -1 else 0)

