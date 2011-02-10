#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, AbortCommit
from calibre.gui2.preferences.tweaks_ui import Ui_Form
from calibre.gui2 import error_dialog, NONE
from calibre.utils.config import read_raw_tweaks, write_tweaks
from calibre.gui2.widgets import PythonHighlighter
from calibre import isbytestring

from PyQt4.Qt import QAbstractListModel, Qt, QStyledItemDelegate, QStyle, \
    QStyleOptionViewItem, QFont, QDialogButtonBox, QDialog, \
    QVBoxLayout, QPlainTextEdit, QLabel

class Delegate(QStyledItemDelegate): # {{{
    def __init__(self, view):
        QStyledItemDelegate.__init__(self, view)
        self.view = view

    def paint(self, p, opt, idx):
        copy = QStyleOptionViewItem(opt)
        copy.showDecorationSelected = True
        if self.view.currentIndex() == idx:
            copy.state |= QStyle.State_HasFocus
        QStyledItemDelegate.paint(self, p, copy, idx)

# }}}

class Tweak(object): # {{{

    def __init__(self, name, doc, var_names, defaults, custom):
        self.name = name
        self.doc = doc.strip()
        self.var_names = var_names
        self.default_values = {}
        for x in var_names:
            self.default_values[x] = defaults[x]
        self.custom_values = {}
        for x in var_names:
            if x in custom:
                self.custom_values[x] = custom[x]

    def __str__(self):
        ans = ['#: ' + self.name]
        for line in self.doc.splitlines():
            if line:
                ans.append('# ' + line)
        for key, val in self.default_values.iteritems():
            val = self.custom_values.get(key, val)
            ans.append('%s = %r'%(key, val))
        ans = '\n'.join(ans)
        if isinstance(ans, unicode):
            ans = ans.encode('utf-8')
        return ans

    def __cmp__(self, other):
        return cmp(self.is_customized, getattr(other, 'is_customized', False))

    @property
    def is_customized(self):
        for x, val in self.default_values.iteritems():
            if self.custom_values.get(x, val) != val:
                return True
        return False

    @property
    def edit_text(self):
        ans = ['# %s'%self.name]
        for x, val in self.default_values.iteritems():
            val = self.custom_values.get(x, val)
            ans.append('%s = %r'%(x, val))
        return '\n\n'.join(ans)

    def restore_to_default(self):
        self.custom_values.clear()

    def update(self, varmap):
        self.custom_values.update(varmap)

# }}}

class Tweaks(QAbstractListModel): # {{{

    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        raw_defaults, raw_custom = read_raw_tweaks()

        self.parse_tweaks(raw_defaults, raw_custom)

    def rowCount(self, *args):
        return len(self.tweaks)

    def data(self, index, role):
        row = index.row()
        try:
            tweak = self.tweaks[row]
        except:
            return NONE
        if role == Qt.DisplayRole:
            return textwrap.fill(tweak.name, 40)
        if role == Qt.FontRole and tweak.is_customized:
            ans = QFont()
            ans.setBold(True)
            return ans
        if role == Qt.ToolTipRole:
            tt = _('This tweak has it default value')
            if tweak.is_customized:
                tt = _('This tweak has been customized')
            return tt
        if role == Qt.UserRole:
            return tweak
        return NONE

    def parse_tweaks(self, defaults, custom):
        l, g = {}, {}
        try:
            exec custom in g, l
        except:
            print 'Failed to load custom tweaks file'
            import traceback
            traceback.print_exc()
        dl, dg = {}, {}
        exec defaults in dg, dl
        lines = defaults.splitlines()
        pos = 0
        self.tweaks = []
        while pos < len(lines):
            line = lines[pos]
            if line.startswith('#:'):
                pos = self.read_tweak(lines, pos, dl, l)
            pos += 1

        default_keys = set(dl.iterkeys())
        custom_keys = set(l.iterkeys())

        self.plugin_tweaks = {}
        for key in custom_keys - default_keys:
            self.plugin_tweaks[key] = l[key]

    def read_tweak(self, lines, pos, defaults, custom):
        name = lines[pos][2:].strip()
        doc, var_names = [], []
        while True:
            pos += 1
            line = lines[pos]
            if not line.startswith('#'):
                break
            doc.append(line[1:].strip())
        doc = '\n'.join(doc)
        while True:
            line = lines[pos]
            if not line.strip():
                break
            spidx1 = line.find(' ')
            spidx2 = line.find('=')
            spidx = spidx1 if spidx1 > 0 and (spidx2 == 0 or spidx2 > spidx1) else spidx2
            if spidx > 0:
                var = line[:spidx]
                if var not in defaults:
                    raise ValueError('%r not in default tweaks dict'%var)
                var_names.append(var)
            pos += 1
        if not var_names:
            raise ValueError('Failed to find any variables for %r'%name)
        self.tweaks.append(Tweak(name, doc, var_names, defaults, custom))
        #print '\n\n', self.tweaks[-1]
        return pos

    def restore_to_default(self, idx):
        tweak = self.data(idx, Qt.UserRole)
        if tweak is not NONE:
            tweak.restore_to_default()
            self.dataChanged.emit(idx, idx)

    def restore_to_defaults(self):
        for r in range(self.rowCount()):
            self.restore_to_default(self.index(r))

    def update_tweak(self, idx, varmap):
        tweak = self.data(idx, Qt.UserRole)
        if tweak is not NONE:
            tweak.update(varmap)
            self.dataChanged.emit(idx, idx)

    def to_string(self):
        ans = ['#!/usr/bin/env python',
               '# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai', '',
               '# This file was automatically generated by calibre, do not'
               ' edit it unless you know what you are doing.', '',
            ]
        for tweak in self.tweaks:
            ans.extend(['', str(tweak), ''])

        if self.plugin_tweaks:
            ans.extend(['', '',
                '# The following are tweaks for installed plugins', ''])
            for key, val in self.plugin_tweaks.iteritems():
                ans.extend(['%s = %r'%(key, val), '', ''])
        return '\n'.join(ans)

    @property
    def plugin_tweaks_string(self):
        ans = []
        for key, val in self.plugin_tweaks.iteritems():
            ans.extend(['%s = %r'%(key, val), '', ''])
        ans = '\n'.join(ans)
        if isbytestring(ans):
            ans = ans.decode('utf-8')
        return ans

    def set_plugin_tweaks(self, d):
        self.plugin_tweaks = d

# }}}

class PluginTweaks(QDialog): # {{{

    def __init__(self, raw, parent=None):
        QDialog.__init__(self, parent)
        self.edit = QPlainTextEdit(self)
        self.highlighter = PythonHighlighter(self.edit.document())
        self.l = QVBoxLayout()
        self.setLayout(self.l)
        self.l.addWidget(QLabel(
            _('Add/edit tweaks for any custom plugins you have installed.')))
        self.l.addWidget(self.edit)
        self.edit.setPlainText(raw)
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel,
                Qt.Horizontal, self)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.l.addWidget(self.bb)
        self.resize(550, 300)

# }}}

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.delegate = Delegate(self.tweaks_view)
        self.tweaks_view.setItemDelegate(self.delegate)
        self.tweaks_view.currentChanged = self.current_changed
        self.highlighter = PythonHighlighter(self.edit_tweak.document())
        self.restore_default_button.clicked.connect(self.restore_to_default)
        self.apply_button.clicked.connect(self.apply_tweak)
        self.plugin_tweaks_button.clicked.connect(self.plugin_tweaks)

    def plugin_tweaks(self):
        raw = self.tweaks.plugin_tweaks_string
        d = PluginTweaks(raw, self)
        if d.exec_() == d.Accepted:
            g, l = {}, {}
            try:
                exec unicode(d.edit.toPlainText()) in g, l
            except:
                import traceback
                return error_dialog(self, _('Failed'),
                    _('There was a syntax error in your tweak. Click '
                        'the show details button for details.'), show=True,
                    det_msg=traceback.format_exc())
            self.tweaks.set_plugin_tweaks(l)
            self.changed()

    def current_changed(self, current, previous):
        tweak = self.tweaks.data(current, Qt.UserRole)
        self.help.setPlainText(tweak.doc)
        self.edit_tweak.setPlainText(tweak.edit_text)

    def changed(self, *args):
        self.changed_signal.emit()

    def initialize(self):
        self.tweaks = Tweaks()
        self.tweaks_view.setModel(self.tweaks)

    def restore_to_default(self, *args):
        idx = self.tweaks_view.currentIndex()
        if idx.isValid():
            self.tweaks.restore_to_default(idx)
            tweak = self.tweaks.data(idx, Qt.UserRole)
            self.edit_tweak.setPlainText(tweak.edit_text)
            self.changed()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.tweaks.restore_to_defaults()
        self.changed()

    def apply_tweak(self):
        idx = self.tweaks_view.currentIndex()
        if idx.isValid():
            l, g = {}, {}
            try:
                exec unicode(self.edit_tweak.toPlainText()) in g, l
            except:
                import traceback
                error_dialog(self.gui, _('Failed'),
                        _('There was a syntax error in your tweak. Click '
                            'the show details button for details.'),
                        det_msg=traceback.format_exc(), show=True)
                return
            self.tweaks.update_tweak(idx, l)
            self.changed()

    def commit(self):
        raw = self.tweaks.to_string()
        try:
            exec raw
        except:
            import traceback
            error_dialog(self, _('Invalid tweaks'),
                    _('The tweaks you entered are invalid, try resetting the'
                        ' tweaks to default and changing them one by one until'
                        ' you find the invalid setting.'),
                    det_msg=traceback.format_exc(), show=True)
            raise AbortCommit('abort')
        write_tweaks(raw)
        ConfigWidgetBase.commit(self)
        return True


if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    #Tweaks()
    #test_widget
    test_widget('Advanced', 'Tweaks')

