__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Miscellaneous widgets used in the GUI
'''
import re, os, traceback

from PyQt4.Qt import QListView, QIcon, QFont, QLabel, QListWidget, \
                        QListWidgetItem, QTextCharFormat, QApplication, \
                        QSyntaxHighlighter, QCursor, QColor, QWidget, \
                        QPixmap, QPalette, QSplitterHandle, QToolButton, \
                        QAbstractListModel, QVariant, Qt, SIGNAL, pyqtSignal, \
                        QRegExp, QSettings, QSize, QModelIndex, QSplitter, \
                        QAbstractButton, QPainter, QLineEdit, QComboBox, \
                        QMenu, QStringListModel, QCompleter, QStringList, \
                        QTimer

from calibre.gui2 import NONE, error_dialog, pixmap_to_data, gprefs

from calibre.gui2.filename_pattern_ui import Ui_Form
from calibre import fit_image, human_readable
from calibre.utils.fonts import fontconfig
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata.meta import metadata_from_filename
from calibre.utils.config import prefs, XMLConfig
from calibre.gui2.progress_indicator import ProgressIndicator as _ProgressIndicator
from calibre.constants import filesystem_encoding

history = XMLConfig('history')

class ProgressIndicator(QWidget):

    def __init__(self, *args):
        QWidget.__init__(self, *args)
        self.setGeometry(0, 0, 300, 350)
        self.pi = _ProgressIndicator(self)
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignHCenter|Qt.AlignTop)
        self.setVisible(False)

    def start(self, msg=''):
        view = self.parent()
        pwidth, pheight = view.size().width(), view.size().height()
        self.resize(pwidth, min(pheight, 250))
        self.move(0, (pheight-self.size().height())/2.)
        self.pi.resize(self.pi.sizeHint())
        self.pi.move(int((self.size().width()-self.pi.size().width())/2.), 0)
        self.status.resize(self.size().width(), self.size().height()-self.pi.size().height()-10)
        self.status.move(0, self.pi.size().height()+10)
        self.status.setText('<h1>'+msg+'</h1>')
        self.setVisible(True)
        self.pi.startAnimation()

    def stop(self):
        self.pi.stopAnimation()
        self.setVisible(False)

class FilenamePattern(QWidget, Ui_Form):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setupUi(self)

        self.connect(self.test_button, SIGNAL('clicked()'), self.do_test)
        self.connect(self.re, SIGNAL('returnPressed()'), self.do_test)
        self.re.setText(prefs['filename_pattern'])

    def do_test(self):
        try:
            pat = self.pattern()
        except Exception, err:
            error_dialog(self, _('Invalid regular expression'),
                         _('Invalid regular expression: %s')%err).exec_()
            return
        mi = metadata_from_filename(unicode(self.filename.text()), pat)
        if mi.title:
            self.title.setText(mi.title)
        else:
            self.title.setText(_('No match'))
        if mi.authors:
            self.authors.setText(', '.join(mi.authors))
        else:
            self.authors.setText(_('No match'))

        if mi.series:
            self.series.setText(mi.series)
        else:
            self.series.setText(_('No match'))

        if mi.series_index is not None:
            self.series_index.setText(str(mi.series_index))
        else:
            self.series_index.setText(_('No match'))

        self.isbn.setText(_('No match') if mi.isbn is None else str(mi.isbn))


    def pattern(self):
        pat = unicode(self.re.text())
        return re.compile(pat)

    def commit(self):
        pat = self.pattern().pattern
        prefs['filename_pattern'] = pat
        return pat


IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'gif', 'png', 'bmp']

class FormatList(QListWidget):
    DROPABBLE_EXTENSIONS = BOOK_EXTENSIONS

    @classmethod
    def paths_from_event(cls, event):
        '''
        Accept a drop event and return a list of paths that can be read from
        and represent files with extensions.
        '''
        if event.mimeData().hasFormat('text/uri-list'):
            urls = [unicode(u.toLocalFile()) for u in event.mimeData().urls()]
            urls = [u for u in urls if os.path.splitext(u)[1] and os.access(u, os.R_OK)]
            return [u for u in urls if os.path.splitext(u)[1][1:].lower() in cls.DROPABBLE_EXTENSIONS]

    def dragEnterEvent(self, event):
        if int(event.possibleActions() & Qt.CopyAction) + \
           int(event.possibleActions() & Qt.MoveAction) == 0:
            return
        paths = self.paths_from_event(event)
        if paths:
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self.paths_from_event(event)
        event.setDropAction(Qt.CopyAction)
        self.emit(SIGNAL('formats_dropped(PyQt_PyObject,PyQt_PyObject)'),
                event, paths)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.emit(SIGNAL('delete_format()'))
        else:
            return QListWidget.keyPressEvent(self, event)


class ImageView(QLabel):

    MAX_WIDTH  = 400
    MAX_HEIGHT = 300
    DROPABBLE_EXTENSIONS = IMAGE_EXTENSIONS

    @classmethod
    def paths_from_event(cls, event):
        '''
        Accept a drop event and return a list of paths that can be read from
        and represent files with extensions.
        '''
        if event.mimeData().hasFormat('text/uri-list'):
            urls = [unicode(u.toLocalFile()) for u in event.mimeData().urls()]
            urls = [u for u in urls if os.path.splitext(u)[1] and os.access(u, os.R_OK)]
            return [u for u in urls if os.path.splitext(u)[1][1:].lower() in cls.DROPABBLE_EXTENSIONS]

    def dragEnterEvent(self, event):
        if int(event.possibleActions() & Qt.CopyAction) + \
           int(event.possibleActions() & Qt.MoveAction) == 0:
            return
        paths = self.paths_from_event(event)
        if paths:
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self.paths_from_event(event)
        event.setDropAction(Qt.CopyAction)
        for path in paths:
            pmap = QPixmap()
            pmap.load(path)
            if not pmap.isNull():
                self.setPixmap(pmap)
                event.accept()
                self.emit(SIGNAL('cover_changed(PyQt_PyObject)'), open(path,
                    'rb').read())
                break

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def setPixmap(self, pixmap):
        QLabel.setPixmap(self, pixmap)
        width, height = fit_image(pixmap.width(), pixmap.height(), self.MAX_WIDTH, self.MAX_HEIGHT)[1:]
        self.setMaximumWidth(width)
        self.setMaximumHeight(height)

    def contextMenuEvent(self, ev):
        cm = QMenu(self)
        copy = cm.addAction(_('Copy Image'))
        paste = cm.addAction(_('Paste Image'))
        if not QApplication.instance().clipboard().mimeData().hasImage():
            paste.setEnabled(False)
        copy.triggered.connect(self.copy_to_clipboard)
        paste.triggered.connect(self.paste_from_clipboard)
        cm.exec_(ev.globalPos())

    def copy_to_clipboard(self):
        QApplication.instance().clipboard().setPixmap(self.pixmap())

    def paste_from_clipboard(self):
        cb = QApplication.instance().clipboard()
        pmap = cb.pixmap()
        if pmap.isNull() and cb.supportsSelection():
            pmap = cb.pixmap(cb.Selection)
        if not pmap.isNull():
            self.setPixmap(pmap)
            self.emit(SIGNAL('cover_changed(PyQt_PyObject)'),
                    pixmap_to_data(pmap))


class LocationModel(QAbstractListModel):

    def __init__(self, parent):
        QAbstractListModel.__init__(self, parent)
        self.icons = [QVariant(QIcon(I('library.png'))),
                      QVariant(QIcon(I('reader.svg'))),
                      QVariant(QIcon(I('sd.svg'))),
                      QVariant(QIcon(I('sd.svg')))]
        self.text = [_('Library\n%d\nbooks'),
                     _('Reader\n%s\navailable'),
                     _('Card A\n%s\navailable'),
                     _('Card B\n%s\navailable')]
        self.free = [-1, -1, -1]
        self.count = 0
        self.highlight_row = 0
        self.library_tooltip = _('Click to see the books available on your computer')
        self.tooltips = [
                         self.library_tooltip,
                         _('Click to see the books in the main memory of your reader'),
                         _('Click to see the books on storage card A in your reader'),
                         _('Click to see the books on storage card B in your reader')
                         ]

    def database_changed(self, db):
        lp = db.library_path
        if not isinstance(lp, unicode):
            lp = lp.decode(filesystem_encoding, 'replace')
        self.tooltips[0] = self.library_tooltip + '\n\n' + \
                _('Books located at') + ' ' + lp
        self.dataChanged.emit(self.index(0), self.index(0))

    def rowCount(self, *args):
        return 1 + len([i for i in self.free if i >= 0])

    def get_device_row(self, row):
        if row == 2 and self.free[1] == -1 and self.free[2] > -1:
            row = 3
        return row

    def data(self, index, role):
        row = index.row()
        drow = self.get_device_row(row)
        data = NONE
        if role == Qt.DisplayRole:
            text = self.text[drow]%(human_readable(self.free[drow-1])) if row > 0 \
                            else self.text[drow]%self.count
            data = QVariant(text)
        elif role == Qt.DecorationRole:
            data = self.icons[drow]
        elif role == Qt.ToolTipRole:
            data = QVariant(self.tooltips[drow])
        elif role == Qt.SizeHintRole:
            data = QVariant(QSize(155, 90))
        elif role == Qt.FontRole:
            font = QFont('monospace')
            font.setBold(row == self.highlight_row)
            data = QVariant(font)
        elif role == Qt.ForegroundRole and row == self.highlight_row:
            return QVariant(QApplication.palette().brush(
                QPalette.HighlightedText))
        elif role == Qt.BackgroundRole and row == self.highlight_row:
            return QVariant(QApplication.palette().brush(
                QPalette.Highlight))

        return data

    def device_connected(self, dev):
        self.icons[1] = QIcon(dev.icon)
        self.dataChanged.emit(self.index(1), self.index(1))

    def headerData(self, section, orientation, role):
        return NONE

    def update_devices(self, cp=(None, None), fs=[-1, -1, -1]):
        if cp is None:
            cp = (None, None)
        if isinstance(cp, (str, unicode)):
            cp = (cp, None)
        if len(fs) < 3:
            fs = list(fs) + [0]
        self.free[0] = fs[0]
        self.free[1] = fs[1]
        self.free[2] = fs[2]
        cpa, cpb = cp
        self.free[1] = fs[1] if fs[1] is not None and cpa is not None else -1
        self.free[2] = fs[2] if fs[2] is not None and cpb is not None else -1
        self.reset()
        self.emit(SIGNAL('devicesChanged()'))

    def location_changed(self, row):
        self.highlight_row = row
        self.emit(SIGNAL('dataChanged(QModelIndex,QModelIndex)'),
                self.index(0), self.index(self.rowCount(QModelIndex())-1))

    def location_for_row(self, row):
        if row == 0: return 'library'
        if row == 1: return 'main'
        if row == 3: return 'cardb'
        return 'carda' if self.free[1] > -1 else 'cardb'

class LocationView(QListView):

    def __init__(self, parent):
        QListView.__init__(self, parent)
        self.setModel(LocationModel(self))
        self.reset()
        self.currentChanged = self.current_changed

        self.eject_button = EjectButton(self)
        self.eject_button.hide()

        self.connect(self, SIGNAL('entered(QModelIndex)'), self.item_entered)
        self.connect(self, SIGNAL('viewportEntered()'), self.viewport_entered)
        self.connect(self.eject_button, SIGNAL('clicked()'), lambda: self.emit(SIGNAL('umount_device()')))
        self.connect(self.model(), SIGNAL('devicesChanged()'), self.eject_button.hide)

    def count_changed(self, new_count):
        self.model().count = new_count
        self.model().reset()

    def current_changed(self, current, previous):
        if current.isValid():
            i = current.row()
            location = self.model().location_for_row(i)
            self.emit(SIGNAL('location_selected(PyQt_PyObject)'), location)
            self.model().location_changed(i)

    def location_changed(self, row):
        if 0 <= row and row <= 3:
            self.model().location_changed(row)

    def leaveEvent(self, event):
        self.unsetCursor()
        self.eject_button.hide()

    def item_entered(self, location):
        self.setCursor(Qt.PointingHandCursor)
        self.eject_button.hide()

        if location.row() == 1:
            rect = self.visualRect(location)

            self.eject_button.resize(rect.height()/2, rect.height()/2)

            x, y = rect.left(), rect.top()
            x = x + (rect.width() - self.eject_button.width() - 2)
            y += 6

            self.eject_button.move(x, y)
            self.eject_button.show()

    def viewport_entered(self):
        self.unsetCursor()
        self.eject_button.hide()


class EjectButton(QAbstractButton):

    def __init__(self, parent):
        QAbstractButton.__init__(self, parent)
        self.mouse_over = False

    def enterEvent(self, event):
        self.mouse_over = True

    def leaveEvent(self, event):
        self.mouse_over = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setClipRect(event.rect())
        image = QPixmap(I('eject')).scaledToHeight(event.rect().height(),
            Qt.SmoothTransformation)

        if not self.mouse_over:
            alpha_mask = QPixmap(image.width(), image.height())
            color = QColor(128, 128, 128)
            alpha_mask.fill(color)
            image.setAlphaChannel(alpha_mask)

        painter.drawPixmap(0, 0, image)




class FontFamilyModel(QAbstractListModel):

    def __init__(self, *args):
        QAbstractListModel.__init__(self, *args)
        try:
            self.families = fontconfig.find_font_families()
        except:
            self.families = []
            print 'WARNING: Could not load fonts'
            traceback.print_exc()
        self.families.sort()
        self.families[:0] = [_('None')]

    def rowCount(self, *args):
        return len(self.families)

    def data(self, index, role):
        try:
            family = self.families[index.row()]
        except:
            traceback.print_exc()
            return NONE
        if role == Qt.DisplayRole:
            return QVariant(family)
        if role == Qt.FontRole:
            return QVariant(QFont(family))
        return NONE

    def index_of(self, family):
        return self.families.index(family.strip())

class BasicComboModel(QAbstractListModel):

    def __init__(self, items, *args):
        QAbstractListModel.__init__(self, *args)
        self.items = [i for i in items]
        self.items.sort()

    def rowCount(self, *args):
        return len(self.items)

    def data(self, index, role):
        try:
            item = self.items[index.row()]
        except:
            traceback.print_exc()
            return NONE
        if role == Qt.DisplayRole:
            return QVariant(item)
        if role == Qt.FontRole:
            return QVariant(QFont(item))
        return NONE

    def index_of(self, item):
        return self.items.index(item.strip())


class BasicListItem(QListWidgetItem):

    def __init__(self, text, user_data=None):
        QListWidgetItem.__init__(self, text)
        self.user_data = user_data

    def __eq__(self, other):
        if hasattr(other, 'text'):
            return self.text() == other.text()
        return False

class BasicList(QListWidget):

    def add_item(self, text, user_data=None, replace=False):
        item = BasicListItem(text, user_data)

        for oitem in self.items():
            if oitem == item:
                if replace:
                    self.takeItem(self.row(oitem))
                else:
                    raise ValueError('Item already in list')

        self.addItem(item)

    def remove_selected_items(self, *args):
        for item in self.selectedItems():
            self.takeItem(self.row(item))

    def items(self):
        for i in range(self.count()):
            yield self.item(i)


class LineEditECM(object):

    '''
    Extend the context menu of a QLineEdit to include more actions.
    '''

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        case_menu = QMenu(_('Change Case'))
        action_upper_case = case_menu.addAction(_('Upper Case'))
        action_lower_case = case_menu.addAction(_('Lower Case'))
        action_swap_case = case_menu.addAction(_('Swap Case'))
        action_title_case = case_menu.addAction(_('Title Case'))

        self.connect(action_upper_case, SIGNAL('triggered()'), self.upper_case)
        self.connect(action_lower_case, SIGNAL('triggered()'), self.lower_case)
        self.connect(action_swap_case, SIGNAL('triggered()'), self.swap_case)
        self.connect(action_title_case, SIGNAL('triggered()'), self.title_case)

        menu.addMenu(case_menu)
        menu.exec_(event.globalPos())

    def upper_case(self):
        self.setText(unicode(self.text()).upper())

    def lower_case(self):
        self.setText(unicode(self.text()).lower())

    def swap_case(self):
        self.setText(unicode(self.text()).swapcase())

    def title_case(self):
        from calibre.utils.titlecase import titlecase
        self.setText(titlecase(unicode(self.text())))


class EnLineEdit(LineEditECM, QLineEdit):

    '''
    Enhanced QLineEdit.

    Includes an extended content menu.
    '''

    pass


class TagsCompleter(QCompleter):

    '''
    A completer object that completes a list of tags. It is used in conjunction
    with a CompleterLineEdit.
    '''

    def __init__(self, parent, all_tags):
        QCompleter.__init__(self, all_tags, parent)
        self.all_tags = set(all_tags)

    def update(self, text_tags, completion_prefix):
        tags = list(self.all_tags.difference(text_tags))
        model = QStringListModel(tags, self)
        self.setModel(model)

        self.setCompletionPrefix(completion_prefix)
        if completion_prefix.strip() != '':
            self.complete()

    def update_tags_cache(self, tags):
        self.all_tags = set(tags)
        model = QStringListModel(tags, self)
        self.setModel(model)


class TagsLineEdit(EnLineEdit):

    '''
    A QLineEdit that can complete parts of text separated by separator.
    '''

    def __init__(self, parent=0, tags=[]):
        EnLineEdit.__init__(self, parent)

        self.separator = ','

        self.connect(self, SIGNAL('textChanged(QString)'), self.text_changed)

        self.completer = TagsCompleter(self, tags)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)

        self.connect(self,
            SIGNAL('text_changed(PyQt_PyObject, PyQt_PyObject)'),
            self.completer.update)
        self.connect(self.completer, SIGNAL('activated(QString)'),
            self.complete_text)

        self.completer.setWidget(self)

    def update_tags_cache(self, tags):
        self.completer.update_tags_cache(tags)

    def text_changed(self, text):
        all_text = unicode(text)
        text = all_text[:self.cursorPosition()]
        prefix = text.split(',')[-1].strip()

        text_tags = []
        for t in all_text.split(self.separator):
            t1 = unicode(t).strip()
            if t1 != '':
                text_tags.append(t)
        text_tags = list(set(text_tags))

        self.emit(SIGNAL('text_changed(PyQt_PyObject, PyQt_PyObject)'),
            text_tags, prefix)

    def complete_text(self, text):
        cursor_pos = self.cursorPosition()
        before_text = unicode(self.text())[:cursor_pos]
        after_text = unicode(self.text())[cursor_pos:]
        prefix_len = len(before_text.split(',')[-1].strip())
        self.setText('%s%s%s %s' % (before_text[:cursor_pos - prefix_len],
            text, self.separator, after_text))
        self.setCursorPosition(cursor_pos - prefix_len + len(text) + 2)


class EnComboBox(QComboBox):

    '''
    Enhanced QComboBox.

    Includes an extended context menu.
    '''

    def __init__(self, *args):
        QComboBox.__init__(self, *args)
        self.setLineEdit(EnLineEdit(self))
        self.setAutoCompletionCaseSensitivity(Qt.CaseSensitive)

    def text(self):
        return unicode(self.currentText())

    def setText(self, text):
        idx = self.findText(text, Qt.MatchFixedString|Qt.MatchCaseSensitive)
        if idx == -1:
            self.insertItem(0, text)
            idx = 0
        self.setCurrentIndex(idx)

class HistoryLineEdit(QComboBox):

    def __init__(self, *args):
        QComboBox.__init__(self, *args)
        self.setEditable(True)
        self.setInsertPolicy(self.NoInsert)
        self.setMaxCount(10)

    @property
    def store_name(self):
        return 'lineedit_history_'+self._name

    def initialize(self, name):
        self._name = name
        self.addItems(QStringList(history.get(self.store_name, [])))
        self.setEditText('')
        self.lineEdit().editingFinished.connect(self.save_history)

    def save_history(self):
        items = []
        ct = unicode(self.currentText())
        if ct:
            items.append(ct)
        for i in range(self.count()):
            item = unicode(self.itemText(i))
            if item not in items:
                items.append(item)

        history.set(self.store_name, items)

    def setText(self, t):
        self.setEditText(t)
        self.lineEdit().setCursorPosition(0)

    def text(self):
        return self.currentText()

class PythonHighlighter(QSyntaxHighlighter):

    Rules = []
    Formats = {}
    Config = {}

    KEYWORDS = ["and", "as", "assert", "break", "class", "continue", "def",
        "del", "elif", "else", "except", "exec", "finally", "for", "from",
        "global", "if", "import", "in", "is", "lambda", "not", "or",
        "pass", "print", "raise", "return", "try", "while", "with",
        "yield"]

    BUILTINS = ["abs", "all", "any", "basestring", "bool", "callable", "chr",
        "classmethod", "cmp", "compile", "complex", "delattr", "dict",
        "dir", "divmod", "enumerate", "eval", "execfile", "exit", "file",
        "filter", "float", "frozenset", "getattr", "globals", "hasattr",
        "hex", "id", "int", "isinstance", "issubclass", "iter", "len",
        "list", "locals", "long", "map", "max", "min", "object", "oct",
        "open", "ord", "pow", "property", "range", "reduce", "repr",
        "reversed", "round", "set", "setattr", "slice", "sorted",
        "staticmethod", "str", "sum", "super", "tuple", "type", "unichr",
        "unicode", "vars", "xrange", "zip"]

    CONSTANTS = ["False", "True", "None", "NotImplemented", "Ellipsis"]


    def __init__(self, parent=None):
        super(PythonHighlighter, self).__init__(parent)
        if not self.Config:
            self.loadConfig()


        self.initializeFormats()

        PythonHighlighter.Rules.append((QRegExp(
                "|".join([r"\b%s\b" % keyword for keyword in self.KEYWORDS])),
                "keyword"))
        PythonHighlighter.Rules.append((QRegExp(
                "|".join([r"\b%s\b" % builtin for builtin in self.BUILTINS])),
                "builtin"))
        PythonHighlighter.Rules.append((QRegExp(
                "|".join([r"\b%s\b" % constant \
                for constant in self.CONSTANTS])), "constant"))
        PythonHighlighter.Rules.append((QRegExp(
                r"\b[+-]?[0-9]+[lL]?\b"
                r"|\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b"
                r"|\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b"),
                "number"))
        PythonHighlighter.Rules.append((QRegExp(
                r"\bPyQt4\b|\bQt?[A-Z][a-z]\w+\b"), "pyqt"))
        PythonHighlighter.Rules.append((QRegExp(r"\b@\w+\b"), "decorator"))
        stringRe = QRegExp(r"""(?:'[^']*'|"[^"]*")""")
        stringRe.setMinimal(True)
        PythonHighlighter.Rules.append((stringRe, "string"))
        self.stringRe = QRegExp(r"""(:?"["]".*"["]"|'''.*''')""")
        self.stringRe.setMinimal(True)
        PythonHighlighter.Rules.append((self.stringRe, "string"))
        self.tripleSingleRe = QRegExp(r"""'''(?!")""")
        self.tripleDoubleRe = QRegExp(r'''"""(?!')''')

    @classmethod
    def loadConfig(cls):
        Config = cls.Config
        settings = QSettings()
        def setDefaultString(name, default):
            value = settings.value(name).toString()
            if value.isEmpty():
                value = default
            Config[name] = value

        for name in ("window", "shell"):
            Config["%swidth" % name] = settings.value("%swidth" % name,
                    QVariant(QApplication.desktop() \
                             .availableGeometry().width() / 2)).toInt()[0]
            Config["%sheight" % name] = settings.value("%sheight" % name,
                    QVariant(QApplication.desktop() \
                             .availableGeometry().height() / 2)).toInt()[0]
            Config["%sy" % name] = settings.value("%sy" % name,
                    QVariant(0)).toInt()[0]
        Config["toolbars"] = settings.value("toolbars").toByteArray()
        Config["splitter"] = settings.value("splitter").toByteArray()
        Config["shellx"] = settings.value("shellx", QVariant(0)).toInt()[0]
        Config["windowx"] = settings.value("windowx", QVariant(QApplication \
                .desktop().availableGeometry().width() / 2)).toInt()[0]
        Config["remembergeometry"] = settings.value("remembergeometry",
                QVariant(True)).toBool()
        Config["startwithshell"] = settings.value("startwithshell",
                QVariant(True)).toBool()
        Config["showwindowinfo"] = settings.value("showwindowinfo",
                QVariant(True)).toBool()
        setDefaultString("shellstartup", """\
    from __future__ import division
    import codecs
    import sys
    sys.stdin = codecs.getreader("UTF8")(sys.stdin)
    sys.stdout = codecs.getwriter("UTF8")(sys.stdout)""")
        setDefaultString("newfile", """\
    #!/usr/bin/env python

    from __future__ import division

    import sys
    """)
        Config["backupsuffix"] = settings.value("backupsuffix",
                QVariant(".bak")).toString()
        setDefaultString("beforeinput", "#>>>")
        setDefaultString("beforeoutput", "#---")
        Config["cwd"] = settings.value("cwd", QVariant(".")).toString()
        Config["tooltipsize"] = settings.value("tooltipsize",
                QVariant(150)).toInt()[0]
        Config["maxlinestoscan"] = settings.value("maxlinestoscan",
                QVariant(5000)).toInt()[0]
        Config["pythondocpath"] = settings.value("pythondocpath",
                QVariant("http://docs.python.org")).toString()
        Config["autohidefinddialog"] = settings.value("autohidefinddialog",
                QVariant(True)).toBool()
        Config["findcasesensitive"] = settings.value("findcasesensitive",
                QVariant(False)).toBool()
        Config["findwholewords"] = settings.value("findwholewords",
                QVariant(False)).toBool()
        Config["tabwidth"] = settings.value("tabwidth",
                QVariant(4)).toInt()[0]
        Config["fontfamily"] = settings.value("fontfamily",
                QVariant("Bitstream Vera Sans Mono")).toString()
        Config["fontsize"] = settings.value("fontsize",
                QVariant(10)).toInt()[0]
        for name, color, bold, italic in (
                ("normal", "#000000", False, False),
                ("keyword", "#000080", True, False),
                ("builtin", "#0000A0", False, False),
                ("constant", "#0000C0", False, False),
                ("decorator", "#0000E0", False, False),
                ("comment", "#007F00", False, True),
                ("string", "#808000", False, False),
                ("number", "#924900", False, False),
                ("error", "#FF0000", False, False),
                ("pyqt", "#50621A", False, False)):
            Config["%sfontcolor" % name] = settings.value(
                    "%sfontcolor" % name, QVariant(color)).toString()
            Config["%sfontbold" % name] = settings.value(
                    "%sfontbold" % name, QVariant(bold)).toBool()
            Config["%sfontitalic" % name] = settings.value(
                    "%sfontitalic" % name, QVariant(italic)).toBool()


    @classmethod
    def initializeFormats(cls):
        Config = cls.Config
        baseFormat = QTextCharFormat()
        baseFormat.setFontFamily(Config["fontfamily"])
        baseFormat.setFontPointSize(Config["fontsize"])
        for name in ("normal", "keyword", "builtin", "constant",
                "decorator", "comment", "string", "number", "error",
                "pyqt"):
            format = QTextCharFormat(baseFormat)
            format.setForeground(QColor(Config["%sfontcolor" % name]))
            if Config["%sfontbold" % name]:
                format.setFontWeight(QFont.Bold)
            format.setFontItalic(Config["%sfontitalic" % name])
            PythonHighlighter.Formats[name] = format


    def highlightBlock(self, text):
        NORMAL, TRIPLESINGLE, TRIPLEDOUBLE, ERROR = range(4)

        textLength = text.length()
        prevState = self.previousBlockState()

        self.setFormat(0, textLength,
                       PythonHighlighter.Formats["normal"])

        if text.startsWith("Traceback") or text.startsWith("Error: "):
            self.setCurrentBlockState(ERROR)
            self.setFormat(0, textLength,
                           PythonHighlighter.Formats["error"])
            return
        if prevState == ERROR and \
           not (text.startsWith('>>>') or text.startsWith("#")):
            self.setCurrentBlockState(ERROR)
            self.setFormat(0, textLength,
                           PythonHighlighter.Formats["error"])
            return

        for regex, format in PythonHighlighter.Rules:
            i = regex.indexIn(text)
            while i >= 0:
                length = regex.matchedLength()
                self.setFormat(i, length,
                               PythonHighlighter.Formats[format])
                i = regex.indexIn(text, i + length)

        # Slow but good quality highlighting for comments. For more
        # speed, comment this out and add the following to __init__:
        #   PythonHighlighter.Rules.append((QRegExp(r"#.*"), "comment"))
        if text.isEmpty():
            pass
        elif text[0] == "#":
            self.setFormat(0, text.length(),
                           PythonHighlighter.Formats["comment"])
        else:
            stack = []
            for i, c in enumerate(text):
                if c in ('"', "'"):
                    if stack and stack[-1] == c:
                        stack.pop()
                    else:
                        stack.append(c)
                elif c == "#" and len(stack) == 0:
                    self.setFormat(i, text.length(),
                                   PythonHighlighter.Formats["comment"])
                    break

        self.setCurrentBlockState(NORMAL)

        if self.stringRe.indexIn(text) != -1:
            return
        # This is fooled by triple quotes inside single quoted strings
        for i, state in ((self.tripleSingleRe.indexIn(text),
                          TRIPLESINGLE),
                         (self.tripleDoubleRe.indexIn(text),
                          TRIPLEDOUBLE)):
            if self.previousBlockState() == state:
                if i == -1:
                    i = text.length()
                    self.setCurrentBlockState(state)
                self.setFormat(0, i + 3,
                               PythonHighlighter.Formats["string"])
            elif i > -1:
                self.setCurrentBlockState(state)
                self.setFormat(i, text.length(),
                               PythonHighlighter.Formats["string"])


    def rehighlight(self):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QSyntaxHighlighter.rehighlight(self)
        QApplication.restoreOverrideCursor()

class SplitterHandle(QSplitterHandle):

    double_clicked = pyqtSignal(object)

    def __init__(self, orientation, splitter):
        QSplitterHandle.__init__(self, orientation, splitter)
        splitter.splitterMoved.connect(self.splitter_moved,
                type=Qt.QueuedConnection)
        self.double_clicked.connect(splitter.double_clicked,
                type=Qt.QueuedConnection)
        self.highlight = False
        self.setToolTip(_('Drag to resize')+' '+splitter.label)

    def splitter_moved(self, *args):
        oh = self.highlight
        self.highlight = 0 in self.splitter().sizes()
        if oh != self.highlight:
            self.update()

    def paintEvent(self, ev):
        QSplitterHandle.paintEvent(self, ev)
        if self.highlight:
            painter = QPainter(self)
            painter.setClipRect(ev.rect())
            painter.fillRect(self.rect(), Qt.yellow)

    def mouseDoubleClickEvent(self, ev):
        self.double_clicked.emit(self)

class LayoutButton(QToolButton):

    def __init__(self, icon, text, splitter, parent=None):
        QToolButton.__init__(self, parent)
        self.label = text
        self.setIcon(QIcon(icon))
        self.setCheckable(True)

        self.splitter = splitter
        splitter.state_changed.connect(self.update_state)
        self.setCursor(Qt.PointingHandCursor)

    def set_state_to_show(self, *args):
        self.setChecked(False)
        label =_('Show')
        self.setText(label + ' ' + self.label)
        self.setToolTip(self.text())

    def set_state_to_hide(self, *args):
        self.setChecked(True)
        label = _('Hide')
        self.setText(label + ' ' + self.label)
        self.setToolTip(self.text())

    def update_state(self, *args):
        if self.splitter.is_side_index_hidden:
            self.set_state_to_show()
        else:
            self.set_state_to_hide()

class Splitter(QSplitter):

    state_changed = pyqtSignal(object)

    def __init__(self, name, label, icon, initial_show=True,
            initial_side_size=120, connect_button=True,
            orientation=Qt.Horizontal, side_index=0, parent=None):
        QSplitter.__init__(self, parent)
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.desired_side_size = initial_side_size
        self.desired_show = initial_show
        self.resize_timer.setInterval(5)
        self.resize_timer.timeout.connect(self.do_resize)
        self.setOrientation(orientation)
        self.side_index = side_index
        self._name = name
        self.label = label
        self.initial_side_size = initial_side_size
        self.initial_show = initial_show
        self.splitterMoved.connect(self.splitter_moved, type=Qt.QueuedConnection)
        self.button = LayoutButton(icon, label, self)
        if connect_button:
            self.button.clicked.connect(self.double_clicked)

    def createHandle(self):
        return SplitterHandle(self.orientation(), self)

    def initialize(self):
        for i in range(self.count()):
            h = self.handle(i)
            if h is not None:
                h.splitter_moved()
        self.state_changed.emit(not self.is_side_index_hidden)

    def splitter_moved(self, *args):
        self.desired_side_size = self.side_index_size
        self.state_changed.emit(not self.is_side_index_hidden)

    @property
    def is_side_index_hidden(self):
        sizes = list(self.sizes())
        return sizes[self.side_index] == 0

    @property
    def save_name(self):
        ori = 'horizontal' if self.orientation() == Qt.Horizontal \
                else 'vertical'
        return self._name + '_' + ori

    def print_sizes(self):
        if self.count() > 1:
            print self.save_name, 'side:', self.side_index_size, 'other:',
            print list(self.sizes())[self.other_index]

    @dynamic_property
    def side_index_size(self):
        def fget(self):
            if self.count() < 2: return 0
            return self.sizes()[self.side_index]

        def fset(self, val):
            if self.count() < 2: return
            if val == 0 and not self.is_side_index_hidden:
                self.save_state()
            sizes = list(self.sizes())
            for i in range(len(sizes)):
                sizes[i] = val if i == self.side_index else 10
            self.setSizes(sizes)
            total = sum(self.sizes())
            sizes = list(self.sizes())
            for i in range(len(sizes)):
                sizes[i] = val if i == self.side_index else total-val
            self.setSizes(sizes)
            self.initialize()

        return property(fget=fget, fset=fset)

    def do_resize(self, *args):
        orig = self.desired_side_size
        QSplitter.resizeEvent(self, self._resize_ev)
        if orig > 20 and self.desired_show:
            c = 0
            while abs(self.side_index_size - orig) > 10 and c < 5:
                self.apply_state(self.get_state(), save_desired=False)
                c += 1

    def resizeEvent(self, ev):
        if self.resize_timer.isActive():
            self.resize_timer.stop()
        self._resize_ev = ev
        self.resize_timer.start()

    def get_state(self):
        if self.count() < 2: return (False, 200)
        return (self.desired_show, self.desired_side_size)

    def apply_state(self, state, save_desired=True):
        if state[0]:
            self.side_index_size = state[1]
            if save_desired:
                self.desired_side_size = self.side_index_size
        else:
            self.side_index_size = 0
        self.desired_show = state[0]

    def default_state(self):
        return (self.initial_show, self.initial_side_size)

    # Public API {{{

    def save_state(self):
        if self.count() > 1:
            gprefs[self.save_name+'_state'] = self.get_state()

    @property
    def other_index(self):
        return (self.side_index+1)%2

    def restore_state(self):
        if self.count() > 1:
            state = gprefs.get(self.save_name+'_state',
                    self.default_state())
            self.apply_state(state, save_desired=False)
            self.desired_side_size = state[1]

    def toggle_side_pane(self, hide=None):
        if hide is None:
            action = 'show' if self.is_side_index_hidden else 'hide'
        else:
            action = 'hide' if hide else 'show'
        getattr(self, action+'_side_pane')()

    def show_side_pane(self):
        if self.count() < 2 or not self.is_side_index_hidden:
            return
        if self.desired_side_size == 0:
            self.desired_side_size = self.initial_side_size
        self.apply_state((True, self.desired_side_size))

    def hide_side_pane(self):
        if self.count() < 2 or self.is_side_index_hidden:
            return
        self.apply_state((False, self.desired_side_size))

    def double_clicked(self, *args):
        self.toggle_side_pane()

    # }}}

