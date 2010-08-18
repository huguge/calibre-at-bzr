#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
from functools import partial

from PyQt4.Qt import QComboBox, QLabel, QSpinBox, QDoubleSpinBox, QDateEdit, \
        QDate, QGroupBox, QVBoxLayout, QPlainTextEdit, QSizePolicy, \
        QSpacerItem, QIcon, QCheckBox, QWidget, QHBoxLayout, SIGNAL, \
        QPushButton, QCoreApplication

from calibre.utils.date import qt_to_dt, now
from calibre.gui2.widgets import TagsLineEdit, EnComboBox
from calibre.gui2 import UNDEFINED_QDATE
from calibre.utils.config import tweaks

class Base(object):

    def __init__(self, db, col_id, parent=None):
        self.db, self.col_id = db, col_id
        self.col_metadata = db.custom_column_num_map[col_id]
        self.initial_val = None
        self.setup_ui(parent)

    def initialize(self, book_id):
        val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
        self.initial_val = val
        val = self.normalize_db_val(val)
        self.setter(val)

    def commit(self, book_id, notify=False):
        val = self.getter()
        val = self.normalize_ui_val(val)
        if val != self.initial_val:
            self.db.set_custom(book_id, val, num=self.col_id, notify=notify)

    def normalize_db_val(self, val):
        return val

    def normalize_ui_val(self, val):
        return val

class Bool(Base):

    def setup_ui(self, parent):
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent),
                QComboBox(parent)]
        w = self.widgets[1]
        items = [_('Yes'), _('No'), _('Undefined')]
        icons = [I('ok.svg'), I('list_remove.svg'), I('blank.svg')]
        if tweaks['bool_custom_columns_are_tristate'] == 'no':
            items = items[:-1]
            icons = icons[:-1]
        for icon, text in zip(icons, items):
            w.addItem(QIcon(icon), text)

    def setter(self, val):
        val = {None: 2, False: 1, True: 0}[val]
        if tweaks['bool_custom_columns_are_tristate'] == 'no' and val == 2:
            val = 1
        self.widgets[1].setCurrentIndex(val)

    def getter(self):
        val = self.widgets[1].currentIndex()
        return {2: None, 1: False, 0: True}[val]

class Int(Base):

    def setup_ui(self, parent):
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent),
                QSpinBox(parent)]
        w = self.widgets[1]
        w.setRange(-100, sys.maxint)
        w.setSpecialValueText(_('Undefined'))
        w.setSingleStep(1)

    def setter(self, val):
        if val is None:
            val = self.widgets[1].minimum()
        else:
            val = int(val)
        self.widgets[1].setValue(val)

    def getter(self):
        val = self.widgets[1].value()
        if val == self.widgets[1].minimum():
            val = None
        return val

class Float(Int):

    def setup_ui(self, parent):
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent),
                QDoubleSpinBox(parent)]
        w = self.widgets[1]
        w.setRange(-100., float(sys.maxint))
        w.setDecimals(2)
        w.setSpecialValueText(_('Undefined'))
        w.setSingleStep(1)

    def setter(self, val):
        if val is None:
            val = self.widgets[1].minimum()
        self.widgets[1].setValue(val)

class Rating(Int):

    def setup_ui(self, parent):
        Int.setup_ui(self, parent)
        w = self.widgets[1]
        w.setRange(0, 5)
        w.setSuffix(' '+_('star(s)'))
        w.setSpecialValueText(_('Unrated'))

    def setter(self, val):
        if val is None:
            val = 0
        self.widgets[1].setValue(int(round(val/2.)))

    def getter(self):
        val = self.widgets[1].value()
        if val == 0:
            val = None
        else:
            val *= 2
        return val

class DateEdit(QDateEdit):

    def focusInEvent(self, x):
        self.setSpecialValueText('')
        QDateEdit.focusInEvent(self, x)

    def focusOutEvent(self, x):
        self.setSpecialValueText(_('Undefined'))
        QDateEdit.focusOutEvent(self, x)

    def set_to_today(self):
        self.setDate(now())

class DateTime(Base):

    def setup_ui(self, parent):
        cm = self.col_metadata
        self.widgets = [QLabel('&'+cm['name']+':', parent), DateEdit(parent),
            QLabel(''), QPushButton(_('Set \'%s\' to today')%cm['name'], parent)]
        w = self.widgets[1]
        format = cm['display'].get('date_format','')
        if not format:
            format = 'dd MMM yyyy'
        w.setDisplayFormat(format)
        w.setCalendarPopup(True)
        w.setMinimumDate(UNDEFINED_QDATE)
        w.setSpecialValueText(_('Undefined'))
        self.widgets[3].clicked.connect(w.set_to_today)

    def setter(self, val):
        if val is None:
            val = self.widgets[1].minimumDate()
        else:
            val = QDate(val.year, val.month, val.day)
        self.widgets[1].setDate(val)

    def getter(self):
        val = self.widgets[1].date()
        if val == UNDEFINED_QDATE:
            val = None
        else:
            val = qt_to_dt(val)
        return val

class Comments(Base):

    def setup_ui(self, parent):
        self._box = QGroupBox(parent)
        self._box.setTitle('&'+self.col_metadata['name'])
        self._layout = QVBoxLayout()
        self._tb = QPlainTextEdit(self._box)
        self._tb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._tb.setTabChangesFocus(True)
        self._layout.addWidget(self._tb)
        self._box.setLayout(self._layout)
        self.widgets = [self._box]

    def setter(self, val):
        if val is None:
            val = ''
        self._tb.setPlainText(val)

    def getter(self):
        val = unicode(self._tb.toPlainText()).strip()
        if not val:
            val = None
        return val

class Text(Base):

    def setup_ui(self, parent):
        values = self.all_values = list(self.db.all_custom(num=self.col_id))
        values.sort(cmp = lambda x,y: cmp(x.lower(), y.lower()))
        if self.col_metadata['is_multiple']:
            w = TagsLineEdit(parent, values)
            w.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        else:
            w = EnComboBox(parent)
            w.setSizeAdjustPolicy(w.AdjustToMinimumContentsLengthWithIcon)
            w.setMinimumContentsLength(25)
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent), w]

    def initialize(self, book_id):
        val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
        self.initial_val = val
        val = self.normalize_db_val(val)
        if self.col_metadata['is_multiple']:
            self.setter(val)
            self.widgets[1].update_tags_cache(self.all_values)
        else:
            idx = None
            for i, c in enumerate(self.all_values):
                if c == val:
                    idx = i
                self.widgets[1].addItem(c)
            self.widgets[1].setEditText('')
            if idx is not None:
                self.widgets[1].setCurrentIndex(idx)

    def setter(self, val):
        if self.col_metadata['is_multiple']:
            if not val:
                val = []
            self.widgets[1].setText(u', '.join(val))

    def getter(self):
        if self.col_metadata['is_multiple']:
            val = unicode(self.widgets[1].text()).strip()
            ans = [x.strip() for x in val.split(',') if x.strip()]
            if not ans:
                ans = None
            return ans
        val = unicode(self.widgets[1].currentText()).strip()
        if not val:
            val = None
        return val

class Series(Base):

    def setup_ui(self, parent):
        values = self.all_values = list(self.db.all_custom(num=self.col_id))
        values.sort(cmp = lambda x,y: cmp(x.lower(), y.lower()))
        w = EnComboBox(parent)
        w.setSizeAdjustPolicy(w.AdjustToMinimumContentsLengthWithIcon)
        w.setMinimumContentsLength(25)
        self.name_widget = w
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent), w]

        self.widgets.append(QLabel('&'+self.col_metadata['name']+_(' index:'), parent))
        w = QDoubleSpinBox(parent)
        w.setRange(-100., float(sys.maxint))
        w.setDecimals(2)
        w.setSpecialValueText(_('Undefined'))
        w.setSingleStep(1)
        self.idx_widget=w
        self.widgets.append(w)

    def initialize(self, book_id):
        val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
        s_index = self.db.get_custom_extra(book_id, num=self.col_id, index_is_id=True)
        if s_index is None:
            s_index = 0.0
        self.idx_widget.setValue(s_index)
        self.initial_index = s_index
        self.initial_val = val
        val = self.normalize_db_val(val)
        idx = None
        for i, c in enumerate(self.all_values):
            if c == val:
                idx = i
            self.name_widget.addItem(c)
        self.name_widget.setEditText('')
        if idx is not None:
            self.widgets[1].setCurrentIndex(idx)

    def commit(self, book_id, notify=False):
        val = unicode(self.name_widget.currentText()).strip()
        val = self.normalize_ui_val(val)
        s_index = self.idx_widget.value()
        if val != self.initial_val or s_index != self.initial_index:
            if s_index == 0.0:
                if tweaks['series_index_auto_increment'] == 'next':
                    s_index = self.db.get_next_cc_series_num_for(val,
                                                             num=self.col_id)
                else:
                    s_index = None
            self.db.set_custom(book_id, val, extra=s_index,
                               num=self.col_id, notify=notify)

widgets = {
        'bool' : Bool,
        'rating' : Rating,
        'int': Int,
        'float': Float,
        'datetime': DateTime,
        'text' : Text,
        'comments': Comments,
        'series': Series,
}

def field_sort(y, z, x=None):
    m1, m2 = x[y], x[z]
    n1 = 'zzzzz' if m1['datatype'] == 'comments' else m1['name']
    n2 = 'zzzzz' if m2['datatype'] == 'comments' else m2['name']
    return cmp(n1.lower(), n2.lower())

def populate_metadata_page(layout, db, book_id, bulk=False, two_column=False, parent=None):
    def widget_factory(type, col):
        if bulk:
            w = bulk_widgets[type](db, col, parent)
        else:
            w = widgets[type](db, col, parent)
        w.initialize(book_id)
        return w
    x = db.custom_column_num_map
    cols = list(x)
    cols.sort(cmp=partial(field_sort, x=x))
    count_non_comment = len([c for c in cols if x[c]['datatype'] != 'comments'])

    layout.setColumnStretch(1, 10)
    if two_column:
        turnover_point = (count_non_comment+1)/2
        layout.setColumnStretch(3, 10)
    else:
        # Avoid problems with multi-line widgets
        turnover_point = count_non_comment + 1000
    ans = []
    column = row = comments_row = 0
    for col in cols:
        dt = x[col]['datatype']
        if dt == 'comments':
            continue
        w = widget_factory(dt, col)
        ans.append(w)
        for c in range(0, len(w.widgets), 2):
            w.widgets[c].setBuddy(w.widgets[c+1])
            layout.addWidget(w.widgets[c], row, column)
            layout.addWidget(w.widgets[c+1], row, column+1)
            row += 1
        comments_row = max(comments_row, row)
        if row >= turnover_point:
            column += 2
            turnover_point = count_non_comment + 1000
            row = 0
    if not bulk: # Add the comments fields
        row = comments_row
        column = 0
        for col in cols:
            dt = x[col]['datatype']
            if dt != 'comments':
                continue
            w = widget_factory(dt, col)
            ans.append(w)
            layout.addWidget(w.widgets[0], row, column, 1, 2)
            if two_column and column == 0:
                column = 2
                continue
            column = 0
            row += 1
    items = []
    if len(ans) > 0:
        items.append(QSpacerItem(10, 10, QSizePolicy.Minimum,
            QSizePolicy.Expanding))
        layout.addItem(items[-1], layout.rowCount(), 0, 1, 1)
        layout.setRowStretch(layout.rowCount()-1, 100)
    return ans, items

class BulkBase(Base):

    def get_initial_value(self, book_ids):
        values = set([])
        for book_id in book_ids:
            val = self.db.get_custom(book_id, num=self.col_id, index_is_id=True)
            if isinstance(val, list):
                val = frozenset(val)
            values.add(val)
            if len(values) > 1:
                break
        ans = None
        if len(values) == 1:
            ans = iter(values).next()
        if isinstance(ans, frozenset):
            ans = list(ans)
        return ans

    def initialize(self, book_ids):
        self.initial_val = val = self.get_initial_value(book_ids)
        val = self.normalize_db_val(val)
        self.setter(val)

    def commit(self, book_ids, notify=False):
        val = self.getter()
        val = self.normalize_ui_val(val)
        if val != self.initial_val:
            self.db.set_custom_bulk(book_ids, val, num=self.col_id, notify=notify)

class BulkBool(BulkBase, Bool):
    pass

class BulkInt(BulkBase, Int):
    pass

class BulkFloat(BulkBase, Float):
    pass

class BulkRating(BulkBase, Rating):
    pass

class BulkDateTime(BulkBase, DateTime):
    pass

class BulkSeries(BulkBase):

    def setup_ui(self, parent):
        values = self.all_values = list(self.db.all_custom(num=self.col_id))
        values.sort(cmp = lambda x,y: cmp(x.lower(), y.lower()))
        w = EnComboBox(parent)
        w.setSizeAdjustPolicy(w.AdjustToMinimumContentsLengthWithIcon)
        w.setMinimumContentsLength(25)
        self.name_widget = w
        self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent), w]

        self.widgets.append(QLabel(_('Automatically number books in this series'), parent))
        self.idx_widget=QCheckBox(parent)
        self.widgets.append(self.idx_widget)

    def initialize(self, book_id):
        self.idx_widget.setChecked(False)
        for c in self.all_values:
            self.name_widget.addItem(c)
        self.name_widget.setEditText('')

    def commit(self, book_ids, notify=False):
        val = unicode(self.name_widget.currentText()).strip()
        val = self.normalize_ui_val(val)
        update_indices = self.idx_widget.checkState()
        if val != '':
            extras = []
            next_index = self.db.get_next_cc_series_num_for(val, num=self.col_id)
            for book_id in book_ids:
                QCoreApplication.processEvents()
                if update_indices:
                    if tweaks['series_index_auto_increment'] == 'next':
                        s_index = next_index
                        next_index += 1
                    else:
                        s_index = 1.0
                else:
                    s_index = self.db.get_custom_extra(book_id, num=self.col_id,
                                                       index_is_id=True)
                extras.append(s_index)
            self.db.set_custom_bulk(book_ids, val, extras=extras,
                                   num=self.col_id, notify=notify)

class RemoveTags(QWidget):

    def __init__(self, parent, values):
        QWidget.__init__(self, parent)
        layout = QHBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tags_box = TagsLineEdit(parent, values)
        layout.addWidget(self.tags_box, stretch = 1)
        # self.tags_box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)

        self.checkbox = QCheckBox(_('Remove all tags'), parent)
        layout.addWidget(self.checkbox)
        self.setLayout(layout)
        self.connect(self.checkbox, SIGNAL('stateChanged(int)'), self.box_touched)

    def box_touched(self, state):
        if state:
            self.tags_box.setText('')
            self.tags_box.setEnabled(False)
        else:
            self.tags_box.setEnabled(True)

class BulkText(BulkBase):

    def setup_ui(self, parent):
        values = self.all_values = list(self.db.all_custom(num=self.col_id))
        values.sort(cmp = lambda x,y: cmp(x.lower(), y.lower()))
        if self.col_metadata['is_multiple']:
            w = TagsLineEdit(parent, values)
            w.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
            self.widgets = [QLabel('&'+self.col_metadata['name']+': ' +
                                   _('tags to add'), parent), w]
            self.adding_widget = w

            w = RemoveTags(parent, values)
            self.widgets.append(QLabel('&'+self.col_metadata['name']+': ' +
                                       _('tags to remove'), parent))
            self.widgets.append(w)
            self.removing_widget = w
        else:
            w = EnComboBox(parent)
            w.setSizeAdjustPolicy(w.AdjustToMinimumContentsLengthWithIcon)
            w.setMinimumContentsLength(25)
            self.widgets = [QLabel('&'+self.col_metadata['name']+':', parent), w]

    def initialize(self, book_ids):
        if self.col_metadata['is_multiple']:
            self.widgets[1].update_tags_cache(self.all_values)
        else:
            val = self.get_initial_value(book_ids)
            self.initial_val = val = self.normalize_db_val(val)
            idx = None
            for i, c in enumerate(self.all_values):
                if c == val:
                    idx = i
                self.widgets[1].addItem(c)
            self.widgets[1].setEditText('')
            if idx is not None:
                self.widgets[1].setCurrentIndex(idx)

    def commit(self, book_ids, notify=False):
        if self.col_metadata['is_multiple']:
            remove = set()
            if self.removing_widget.checkbox.isChecked():
                for book_id in book_ids:
                    remove |= set(self.db.get_custom(book_id, num=self.col_id,
                                                     index_is_id=True))
            else:
                txt = unicode(self.removing_widget.tags_box.text())
                if txt:
                    remove = set([v.strip() for v in txt.split(',')])
            txt = unicode(self.adding_widget.text())
            if txt:
                add = set([v.strip() for v in txt.split(',')])
            else:
                add = set()
            self.db.set_custom_bulk_multiple(book_ids, add=add, remove=remove,
                                            num=self.col_id)
        else:
            val = self.getter()
            val = self.normalize_ui_val(val)
            if val != self.initial_val:
                self.db.set_custom_bulk(book_ids, val, num=self.col_id, notify=notify)

    def getter(self, original_value = None):
        if self.col_metadata['is_multiple']:
            if self.removing_widget.checkbox.isChecked():
                ans = set()
            else:
                ans = set(original_value)
                ans -= set([v.strip() for v in
                            unicode(self.removing_widget.tags_box.text()).split(',')])
            txt = unicode(self.adding_widget.text())
            if txt:
                ans |= set([v.strip() for v in txt.split(',')])
            return ans # returning a set instead of a list works, for now at least.
        val = unicode(self.widgets[1].currentText()).strip()
        if not val:
            val = None
        return val


bulk_widgets = {
        'bool' : BulkBool,
        'rating' : BulkRating,
        'int': BulkInt,
        'float': BulkFloat,
        'datetime': BulkDateTime,
        'text' : BulkText,
        'series': BulkSeries,
}
