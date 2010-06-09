__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to create a new custom column'''

import re
from functools import partial

from PyQt4.QtCore import SIGNAL
from PyQt4.Qt import QDialog, Qt, QListWidgetItem, QVariant

from calibre.gui2.dialogs.config.create_custom_column_ui import Ui_QCreateCustomColumn
from calibre.gui2 import error_dialog

class CreateCustomColumn(QDialog, Ui_QCreateCustomColumn):

    column_types = {
                    0:{'datatype':'text',
                        'text':_('Text, column shown in the tag browser'),
                        'is_multiple':False},
                    1:{'datatype':'*text',
                        'text':_('Comma separated text, like tags, shown in the tag browser'),
                        'is_multiple':True},
                    2:{'datatype':'comments',
                        'text':_('Long text, like comments, not shown in the tag browser'),
                        'is_multiple':False},
                    3:{'datatype':'datetime',
                        'text':_('Date'), 'is_multiple':False},
                    4:{'datatype':'float',
                        'text':_('Floating point numbers'), 'is_multiple':False},
                    5:{'datatype':'int',
                        'text':_('Integers'), 'is_multiple':False},
                    6:{'datatype':'rating',
                        'text':_('Ratings, shown with stars'),
                        'is_multiple':False},
                    7:{'datatype':'bool',
                        'text':_('Yes/No'), 'is_multiple':False},
                }

    def __init__(self, parent, editing, standard_colheads, standard_colnames):
        QDialog.__init__(self, parent)
        Ui_QCreateCustomColumn.__init__(self)
        self.setupUi(self)
        self.simple_error = partial(error_dialog, self, show=True,
            show_copy_button=False)
        self.connect(self.button_box, SIGNAL("accepted()"), self.accept)
        self.connect(self.button_box, SIGNAL("rejected()"), self.reject)
        self.parent = parent
        self.editing_col = editing
        self.standard_colheads = standard_colheads
        self.standard_colnames = standard_colnames
        for t in self.column_types:
            self.column_type_box.addItem(self.column_types[t]['text'])
        self.column_type_box.currentIndexChanged.connect(self.datatype_changed)
        if not self.editing_col:
            self.datatype_changed()
            self.exec_()
            return
        idx = parent.columns.currentRow()
        if idx < 0:
            self.simple_error(_('No column selected'),
                    _('No column has been selected'))
            return
        col = unicode(parent.columns.item(idx).data(Qt.UserRole).toString())
        if col not in parent.custcols:
            self.simple_error('', _('Selected column is not a user-defined column'))
            return

        c = parent.custcols[col]
        self.column_name_box.setText(c['label'])
        self.column_heading_box.setText(c['name'])
        ct = c['datatype'] if not c['is_multiple'] else '*text'
        self.orig_column_number = c['colnum']
        self.orig_column_name = col
        column_numbers = dict(map(lambda x:(self.column_types[x]['datatype'], x), self.column_types))
        self.column_type_box.setCurrentIndex(column_numbers[ct])
        self.column_type_box.setEnabled(False)
        if ct == 'datetime':
            if c['display'].get('date_format', None):
                self.date_format_box.setText(c['display'].get('date_format', ''))
        self.datatype_changed()
        self.exec_()

    def datatype_changed(self, *args):
        try:
            col_type = self.column_types[self.column_type_box.currentIndex()]['datatype']
        except:
            col_type = None
        df_visible = col_type == 'datetime'
        for x in ('box', 'default_label', 'label'):
            getattr(self, 'date_format_'+x).setVisible(df_visible)


    def accept(self):
        col = unicode(self.column_name_box.text()).lower()
        if not col:
            return self.simple_error('', _('No lookup name was provided'))
        if re.match('^\w*$', col) is None or not col[0].isalpha():
            return self.simple_error('', _('The label must contain only letters, digits and underscores, and start with a letter'))
        col_heading = unicode(self.column_heading_box.text())
        col_type = self.column_types[self.column_type_box.currentIndex()]['datatype']
        if col_type == '*text':
            col_type='text'
            is_multiple = True
        else:
            is_multiple = False
        if not col_heading:
            return self.simple_error('', _('No column heading was provided'))
        bad_col = False
        if col in self.parent.custcols:
            if not self.editing_col or self.parent.custcols[col]['colnum'] != self.orig_column_number:
                bad_col = True
        if bad_col:
            return self.simple_error('', _('The lookup name %s is already used')%col)
        bad_head = False
        for t in self.parent.custcols:
            if self.parent.custcols[t]['name'] == col_heading:
                if not self.editing_col or self.parent.custcols[t]['colnum'] != self.orig_column_number:
                    bad_head = True
        for t in self.standard_colheads:
            if self.standard_colheads[t] == col_heading:
                bad_head = True
        if bad_head:
            return self.simple_error('', _('The heading %s is already used')%col_heading)
        if ':' in col or ' ' in col or col.lower() != col:
            return self.simple_error('', _('The lookup name must be lower case and cannot contain ":"s or spaces'))

        date_format = {}
        if col_type == 'datetime':
            if self.date_format_box.text():
                date_format = {'date_format':unicode(self.date_format_box.text())}
            else:
                date_format = {'date_format': None}

        key = self.parent.db.field_metadata.custom_field_prefix+col
        if not self.editing_col:
            self.parent.db.field_metadata
            self.parent.custcols[key] = {
                    'label':col,
                    'name':col_heading,
                    'datatype':col_type,
                    'editable':True,
                    'display':date_format,
                    'normalized':None,
                    'colnum':None,
                    'is_multiple':is_multiple,
                }
            item = QListWidgetItem(col_heading, self.parent.columns)
            item.setData(Qt.UserRole, QVariant(key))
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked)
        else:
            idx = self.parent.columns.currentRow()
            item = self.parent.columns.item(idx)
            item.setData(Qt.UserRole, QVariant(key))
            item.setText(col_heading)
            self.parent.custcols[self.orig_column_name]['label'] = col
            self.parent.custcols[self.orig_column_name]['name'] = col_heading
            self.parent.custcols[self.orig_column_name]['display'].update(date_format)
            self.parent.custcols[self.orig_column_name]['*edited'] = True
            self.parent.custcols[self.orig_column_name]['*must_restart'] = True
        QDialog.accept(self)

    def reject(self):
        QDialog.reject(self)
