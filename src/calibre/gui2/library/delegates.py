#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from math import cos, sin, pi

from PyQt4.Qt import (QColor, Qt, QModelIndex, QSize, QApplication,
                     QPainterPath, QLinearGradient, QBrush,
                     QPen, QStyle, QPainter, QStyleOptionViewItemV4,
                     QIcon,  QDoubleSpinBox, QVariant, QSpinBox,
                     QStyledItemDelegate, QComboBox, QTextDocument,
                     QAbstractTextDocumentLayout)

from calibre.gui2 import UNDEFINED_QDATE, error_dialog
from calibre.gui2.widgets import EnLineEdit
from calibre.gui2.complete import MultiCompleteLineEdit, MultiCompleteComboBox
from calibre.utils.date import now, format_date
from calibre.utils.config import tweaks
from calibre.utils.formatter import validation_formatter
from calibre.utils.icu import sort_key
from calibre.gui2.dialogs.comments_dialog import CommentsDialog
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.languages import LanguagesEdit


class RatingDelegate(QStyledItemDelegate): # {{{
    COLOR    = QColor("blue")
    SIZE     = 16

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self._parent = parent
        self.dummy = QModelIndex()
        self.star_path = QPainterPath()
        self.star_path.moveTo(90, 50)
        for i in range(1, 5):
            self.star_path.lineTo(50 + 40 * cos(0.8 * i * pi), \
                                  50 + 40 * sin(0.8 * i * pi))
        self.star_path.closeSubpath()
        self.star_path.setFillRule(Qt.WindingFill)
        self.gradient = QLinearGradient(0, 0, 0, 100)
        self.factor = self.SIZE/100.

    def sizeHint(self, option, index):
        #num = index.model().data(index, Qt.DisplayRole).toInt()[0]
        return QSize(5*(self.SIZE), self.SIZE+4)

    def paint(self, painter, option, index):
        style = self._parent.style()
        option = QStyleOptionViewItemV4(option)
        self.initStyleOption(option, index)
        option.text = u''
        num = index.model().data(index, Qt.DisplayRole).toInt()[0]
        def draw_star():
            painter.save()
            painter.scale(self.factor, self.factor)
            painter.translate(50.0, 50.0)
            painter.rotate(-20)
            painter.translate(-50.0, -50.0)
            painter.drawPath(self.star_path)
            painter.restore()

        painter.save()
        if hasattr(QStyle, 'CE_ItemViewItem'):
            style.drawControl(QStyle.CE_ItemViewItem, option,
                    painter, self._parent)
        elif option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            painter.fillRect(option.rect, option.backgroundBrush)

        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setClipRect(option.rect)
            y = option.rect.center().y()-self.SIZE/2.
            x = option.rect.left()
            color = index.data(Qt.ForegroundRole)
            if color.isNull() or not color.isValid():
                color = self.COLOR
            else:
                color = QColor(color)
            painter.setPen(QPen(color,  1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            self.gradient.setColorAt(0.0, color)
            self.gradient.setColorAt(1.0, color)
            painter.setBrush(QBrush(self.gradient))
            painter.translate(x, y)
            i = 0
            while i < num:
                draw_star()
                painter.translate(self.SIZE, 0)
                i += 1
        except:
            import traceback
            traceback.print_exc()
        painter.restore()

    def createEditor(self, parent, option, index):
        sb = QStyledItemDelegate.createEditor(self, parent, option, index)
        sb.setMinimum(0)
        sb.setMaximum(5)
        return sb
# }}}

class DateDelegate(QStyledItemDelegate): # {{{

    def __init__(self, parent, tweak_name='gui_timestamp_display_format',
            default_format='dd MMM yyyy', editor_format='dd MMM yyyy'):
        QStyledItemDelegate.__init__(self, parent)
        self.tweak_name = tweak_name
        self.default_format = default_format
        self.editor_format = editor_format

    def displayText(self, val, locale):
        d = val.toDate()
        if d <= UNDEFINED_QDATE:
            return ''
        format = tweaks[self.tweak_name]
        if format is None:
            format = self.default_format
        return format_date(d.toPyDate(), format)

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat(self.editor_format)
        qde.setMinimumDate(UNDEFINED_QDATE)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde
# }}}

class PubDateDelegate(QStyledItemDelegate): # {{{

    def displayText(self, val, locale):
        d = val.toDate()
        if d <= UNDEFINED_QDATE:
            return ''
        format = tweaks['gui_pubdate_display_format']
        if format is None:
            format = 'MMM yyyy'
        return format_date(d.toPyDate(), format)

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat('MM yyyy')
        qde.setMinimumDate(UNDEFINED_QDATE)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde

# }}}

class TextDelegate(QStyledItemDelegate): # {{{
    def __init__(self, parent):
        '''
        Delegate for text data. If auto_complete_function needs to return a list
        of text items to auto-complete with. If the function is None no
        auto-complete will be used.
        '''
        QStyledItemDelegate.__init__(self, parent)
        self.auto_complete_function = None

    def set_auto_complete_function(self, f):
        self.auto_complete_function = f

    def createEditor(self, parent, option, index):
        if self.auto_complete_function:
            editor = MultiCompleteComboBox(parent)
            editor.set_separator(None)
            complete_items = [i[1] for i in self.auto_complete_function()]
            editor.update_items_cache(complete_items)
            for item in sorted(complete_items, key=sort_key):
                editor.addItem(item)
            ct = index.data(Qt.DisplayRole).toString()
            editor.setEditText(ct)
            editor.lineEdit().selectAll()
        else:
            editor = EnLineEdit(parent)
        return editor

    def setModelData(self, editor, model, index):
        if isinstance(editor, MultiCompleteComboBox):
            val = editor.lineEdit().text()
            model.setData(index, QVariant(val), Qt.EditRole)
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)

#}}}

class CompleteDelegate(QStyledItemDelegate): # {{{
    def __init__(self, parent, sep, items_func_name, space_before_sep=False):
        QStyledItemDelegate.__init__(self, parent)
        self.sep = sep
        self.items_func_name = items_func_name
        self.space_before_sep = space_before_sep

    def set_database(self, db):
        self.db = db

    def createEditor(self, parent, option, index):
        if self.db and hasattr(self.db, self.items_func_name):
            col = index.model().column_map[index.column()]
            editor = MultiCompleteComboBox(parent)
            editor.set_separator(self.sep)
            editor.set_space_before_sep(self.space_before_sep)
            if self.sep == '&':
                editor.set_add_separator(tweaks['authors_completer_append_separator'])
            if not index.model().is_custom_column(col):
                all_items = getattr(self.db, self.items_func_name)()
            else:
                all_items = list(self.db.all_custom(
                    label=self.db.field_metadata.key_to_label(col)))
            editor.update_items_cache(all_items)
            for item in sorted(all_items, key=sort_key):
                editor.addItem(item)
            ct = index.data(Qt.DisplayRole).toString()
            editor.setEditText(ct)
            editor.lineEdit().selectAll()
        else:
            editor = EnLineEdit(parent)
        return editor

    def setModelData(self, editor, model, index):
        if isinstance(editor, MultiCompleteComboBox):
            val = editor.lineEdit().text()
            model.setData(index, QVariant(val), Qt.EditRole)
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)
# }}}

class LanguagesDelegate(QStyledItemDelegate): # {{{

    def createEditor(self, parent, option, index):
        editor = LanguagesEdit(parent=parent)
        editor.init_langs(index.model().db)
        ct = index.data(Qt.DisplayRole).toString()
        editor.setEditText(ct)
        editor.lineEdit().selectAll()
        return editor

    def setModelData(self, editor, model, index):
        val = ','.join(editor.lang_codes)
        model.setData(index, QVariant(val), Qt.EditRole)
# }}}

class CcDateDelegate(QStyledItemDelegate): # {{{
    '''
    Delegate for custom columns dates. Because this delegate stores the
    format as an instance variable, a new instance must be created for each
    column. This differs from all the other delegates.
    '''

    def set_format(self, format):
        if not format:
            self.format = 'dd MMM yyyy'
        else:
            self.format = format

    def displayText(self, val, locale):
        d = val.toDate()
        if d <= UNDEFINED_QDATE:
            return ''
        return format_date(d.toPyDate(), self.format)

    def createEditor(self, parent, option, index):
        qde = QStyledItemDelegate.createEditor(self, parent, option, index)
        qde.setDisplayFormat(self.format)
        qde.setMinimumDate(UNDEFINED_QDATE)
        qde.setSpecialValueText(_('Undefined'))
        qde.setCalendarPopup(True)
        return qde

    def setEditorData(self, editor, index):
        m = index.model()
        # db col is not named for the field, but for the table number. To get it,
        # gui column -> column label -> table number -> db column
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if val is None:
            val = now()
        editor.setDate(val)

    def setModelData(self, editor, model, index):
        val = editor.date()
        if val <= UNDEFINED_QDATE:
            val = None
        model.setData(index, QVariant(val), Qt.EditRole)

# }}}

class CcTextDelegate(QStyledItemDelegate): # {{{
    '''
    Delegate for text data.
    '''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        editor = MultiCompleteLineEdit(parent)
        editor.set_separator(None)
        complete_items = sorted(list(m.db.all_custom(label=m.db.field_metadata.key_to_label(col))),
                                key=sort_key)
        editor.update_items_cache(complete_items)
        return editor

# }}}

class CcNumberDelegate(QStyledItemDelegate): # {{{
    '''
    Delegate for text/int/float data.
    '''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        if m.custom_columns[col]['datatype'] == 'int':
            editor = QSpinBox(parent)
            editor.setRange(-1000000, 100000000)
            editor.setSpecialValueText(_('Undefined'))
            editor.setSingleStep(1)
        else:
            editor = QDoubleSpinBox(parent)
            editor.setSpecialValueText(_('Undefined'))
            editor.setRange(-1000000., 100000000)
            editor.setDecimals(2)
        return editor

    def setModelData(self, editor, model, index):
        val = editor.value()
        if val == editor.minimum():
            val = None
        model.setData(index, QVariant(val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if val is None:
            val = 0
        editor.setValue(val)

# }}}

class CcEnumDelegate(QStyledItemDelegate): # {{{
    '''
    Delegate for text/int/float data.
    '''

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        editor = DelegateCB(parent)
        editor.addItem('')
        for v in m.custom_columns[col]['display']['enum_values']:
            editor.addItem(v)
        return editor

    def setModelData(self, editor, model, index):
        val = unicode(editor.currentText())
        if not val:
            val = None
        model.setData(index, QVariant(val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if val is None:
            val = ''
        idx = editor.findText(val)
        if idx < 0:
            editor.setCurrentIndex(0)
        else:
            editor.setCurrentIndex(idx)
# }}}

class CcCommentsDelegate(QStyledItemDelegate): # {{{
    '''
    Delegate for comments data.
    '''

    def __init__(self, parent):
        QStyledItemDelegate.__init__(self, parent)
        self.document = QTextDocument()

    def paint(self, painter, option, index):
        self.initStyleOption(option, index)
        style = QApplication.style() if option.widget is None \
                                                else option.widget.style()
        self.document.setHtml(option.text)
        option.text = u''
        if hasattr(QStyle, 'CE_ItemViewItem'):
            style.drawControl(QStyle.CE_ItemViewItem, option, painter)
        ctx = QAbstractTextDocumentLayout.PaintContext()
        ctx.palette = option.palette #.setColor(QPalette.Text, QColor("red"));
        if hasattr(QStyle, 'SE_ItemViewItemText'):
            textRect = style.subElementRect(QStyle.SE_ItemViewItemText, option)
            painter.save()
            painter.translate(textRect.topLeft())
            painter.setClipRect(textRect.translated(-textRect.topLeft()))
            self.document.documentLayout().draw(painter, ctx)
            painter.restore()

    def createEditor(self, parent, option, index):
        m = index.model()
        col = m.column_map[index.column()]
        text = m.db.data[index.row()][m.custom_columns[col]['rec_index']]
        editor = CommentsDialog(parent, text)
        d = editor.exec_()
        if d:
            m.setData(index, QVariant(editor.textbox.html), Qt.EditRole)
        return None

    def setModelData(self, editor, model, index):
        model.setData(index, QVariant(editor.textbox.html), Qt.EditRole)
# }}}

class DelegateCB(QComboBox): # {{{

    def __init__(self, parent):
        QComboBox.__init__(self, parent)

    def event(self, e):
        if e.type() == e.ShortcutOverride:
            e.accept()
        return QComboBox.event(self, e)
# }}}

class CcBoolDelegate(QStyledItemDelegate): # {{{
    def __init__(self, parent):
        '''
        Delegate for custom_column bool data.
        '''
        QStyledItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        editor = DelegateCB(parent)
        items = [_('Y'), _('N'), ' ']
        icons = [I('ok.png'), I('list_remove.png'), I('blank.png')]
        if not index.model().db.prefs.get('bools_are_tristate'):
            items = items[:-1]
            icons = icons[:-1]
        for icon, text in zip(icons, items):
            editor.addItem(QIcon(icon), text)
        return editor

    def setModelData(self, editor, model, index):
        val = {0:True, 1:False, 2:None}[editor.currentIndex()]
        model.setData(index, QVariant(val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.db.data[index.row()][m.custom_columns[m.column_map[index.column()]]['rec_index']]
        if not m.db.prefs.get('bools_are_tristate'):
            val = 1 if not val else 0
        else:
            val = 2 if val is None else 1 if not val else 0
        editor.setCurrentIndex(val)

# }}}

class CcTemplateDelegate(QStyledItemDelegate): # {{{
    def __init__(self, parent):
        '''
        Delegate for custom_column bool data.
        '''
        QStyledItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        m = index.model()
        mi = m.db.get_metadata(index.row(), index_is_id=False)
        text = m.custom_columns[m.column_map[index.column()]]['display']['composite_template']
        editor = TemplateDialog(parent, text, mi)
        editor.setWindowTitle(_("Edit template"))
        editor.textbox.setTabChangesFocus(False)
        editor.textbox.setTabStopWidth(20)
        d = editor.exec_()
        if d:
            m.setData(index, QVariant(editor.rule[1]), Qt.EditRole)
        return None

    def setModelData(self, editor, model, index):
        val = unicode(editor.textbox.toPlainText())
        try:
            validation_formatter.validate(val)
        except Exception as err:
            error_dialog(self.parent(), _('Invalid template'),
                    '<p>'+_('The template %s is invalid:')%val + \
                    '<br>'+str(err), show=True)
        model.setData(index, QVariant(val), Qt.EditRole)

    def setEditorData(self, editor, index):
        m = index.model()
        val = m.custom_columns[m.column_map[index.column()]]['display']['composite_template']
        editor.textbox.setPlainText(val)


# }}}

