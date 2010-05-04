__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
""" The GUI """
import os
from threading import RLock

from PyQt4.QtCore import QVariant, QFileInfo, QObject, SIGNAL, QBuffer, Qt, QSize, \
                         QByteArray, QTranslator, QCoreApplication, QThread, \
                         QEvent, QTimer, pyqtSignal
from PyQt4.QtGui import QFileDialog, QMessageBox, QPixmap, QFileIconProvider, \
                        QIcon, QTableView, QApplication, QDialog, QPushButton

ORG_NAME = 'KovidsBrain'
APP_UID  = 'libprs500'
from calibre import islinux, iswindows, isosx, isfreebsd
from calibre.utils.config import Config, ConfigProxy, dynamic, JSONConfig
from calibre.utils.localization import set_qt_translator
from calibre.ebooks.metadata.meta import get_metadata, metadata_from_formats
from calibre.ebooks.metadata import MetaInformation

gprefs = JSONConfig('gui')

NONE = QVariant() #: Null value to return from the data function of item models

ALL_COLUMNS = ['title', 'authors', 'size', 'timestamp', 'rating', 'publisher',
        'tags', 'series', 'pubdate']

def _config():
    c = Config('gui', 'preferences for the calibre GUI')
    c.add_opt('send_to_storage_card_by_default', default=False,
              help=_('Send file to storage card instead of main memory by default'))
    c.add_opt('confirm_delete', default=False,
              help=_('Confirm before deleting'))
    c.add_opt('toolbar_icon_size', default=QSize(48, 48),
              help=_('Toolbar icon size')) # value QVariant.toSize
    c.add_opt('show_text_in_toolbar', default=True,
              help=_('Show button labels in the toolbar'))
    c.add_opt('main_window_geometry', default=None,
              help=_('Main window geometry')) # value QVariant.toByteArray
    c.add_opt('new_version_notification', default=True,
              help=_('Notify when a new version is available'))
    c.add_opt('use_roman_numerals_for_series_number', default=True,
              help=_('Use Roman numerals for series number'))
    c.add_opt('sort_by_popularity', default=False,
              help=_('Sort tags list by popularity'))
    c.add_opt('cover_flow_queue_length', default=6,
              help=_('Number of covers to show in the cover browsing mode'))
    c.add_opt('LRF_conversion_defaults', default=[],
              help=_('Defaults for conversion to LRF'))
    c.add_opt('LRF_ebook_viewer_options', default=None,
              help=_('Options for the LRF ebook viewer'))
    c.add_opt('internally_viewed_formats', default=['LRF', 'EPUB', 'LIT',
        'MOBI', 'PRC', 'HTML', 'FB2', 'PDB', 'RB'],
              help=_('Formats that are viewed using the internal viewer'))
    c.add_opt('column_map', default=ALL_COLUMNS,
              help=_('Columns to be displayed in the book list'))
    c.add_opt('autolaunch_server', default=False, help=_('Automatically launch content server on application startup'))
    c.add_opt('oldest_news', default=60, help=_('Oldest news kept in database'))
    c.add_opt('systray_icon', default=False, help=_('Show system tray icon'))
    c.add_opt('upload_news_to_device', default=True,
              help=_('Upload downloaded news to device'))
    c.add_opt('delete_news_from_library_on_upload', default=False,
              help=_('Delete books from library after uploading to device'))
    c.add_opt('separate_cover_flow', default=False,
              help=_('Show the cover flow in a separate window instead of in the main calibre window'))
    c.add_opt('disable_tray_notification', default=False,
              help=_('Disable notifications from the system tray icon'))
    c.add_opt('default_send_to_device_action', default=None,
            help=_('Default action to perform when send to device button is '
                'clicked'))
    c.add_opt('show_donate_button', default=True,
            help='Show donation button')
    c.add_opt('asked_library_thing_password', default=False,
            help='Asked library thing password at least once.')
    c.add_opt('search_as_you_type', default=True,
            help='Start searching as you type. If this is disabled then search will '
            'only take place when the Enter or Return key is pressed.')
    c.add_opt('save_to_disk_template_history', default=[],
        help='Previously used Save to Disk templates')
    c.add_opt('send_to_device_template_history', default=[],
        help='Previously used Send to Device templates')
    c.add_opt('main_search_history', default=[],
        help='Search history for the main GUI')
    c.add_opt('viewer_search_history', default=[],
        help='Search history for the ebook viewer')
    c.add_opt('lrf_viewer_search_history', default=[],
        help='Search history for the LRF viewer')
    c.add_opt('scheduler_search_history', default=[],
        help='Search history for the recipe scheduler')
    c.add_opt('worker_limit', default=6,
            help=_('Maximum number of waiting worker processes'))
    c.add_opt('get_social_metadata', default=True,
            help=_('Download social metadata (tags/rating/etc.)'))
    c.add_opt('overwrite_author_title_metadata', default=True,
            help=_('Overwrite author and title with new metadata'))
    c.add_opt('enforce_cpu_limit', default=True,
            help=_('Limit max simultaneous jobs to number of CPUs'))
    c.add_opt('user_categories', default={},
            help=_('User-created tag browser categories'))

    return ConfigProxy(c)

config = _config()
# Turn off DeprecationWarnings in windows GUI
if iswindows:
    import warnings
    warnings.simplefilter('ignore', DeprecationWarning)

def available_heights():
    desktop  = QCoreApplication.instance().desktop()
    return map(lambda x: x.height(), map(desktop.availableGeometry, range(desktop.numScreens())))

def available_height():
    desktop  = QCoreApplication.instance().desktop()
    return desktop.availableGeometry().height()

def max_available_height():
    return max(available_heights())

def min_available_height():
    return min(available_heights())

def available_width():
    desktop       = QCoreApplication.instance().desktop()
    return desktop.availableGeometry().width()

def extension(path):
    return os.path.splitext(path)[1][1:].lower()

class CopyButton(QPushButton):

    ACTION_KEYS = [Qt.Key_Enter, Qt.Key_Return, Qt.Key_Space]

    def copied(self):
        self.emit(SIGNAL('copy()'))
        self.setDisabled(True)
        self.setText(_('Copied'))


    def keyPressEvent(self, ev):
        try:
            if ev.key() in self.ACTION_KEYS:
                self.copied()
                return
        except:
            pass
        QPushButton.keyPressEvent(self, ev)


    def keyReleaseEvent(self, ev):
        try:
            if ev.key() in self.ACTION_KEYS:
                return
        except:
            pass
        QPushButton.keyReleaseEvent(self, ev)

    def mouseReleaseEvent(self, ev):
        ev.accept()
        self.copied()

class MessageBox(QMessageBox):

    def __init__(self, type_, title, msg, buttons, parent, det_msg=''):
        QMessageBox.__init__(self, type_, title, msg, buttons, parent)
        self.title = title
        self.msg = msg
        self.det_msg = det_msg
        self.setDetailedText(det_msg)
        # Cannot set keyboard shortcut as the event is not easy to filter
        self.cb = CopyButton(_('Copy') if isosx else _('Copy to Clipboard'))
        self.connect(self.cb, SIGNAL('copy()'), self.copy_to_clipboard)
        self.addButton(self.cb, QMessageBox.ActionRole)
        default_button = self.button(self.Ok)
        if default_button is None:
            default_button = self.button(self.Yes)
        if default_button is not None:
            self.setDefaultButton(default_button)


    def copy_to_clipboard(self):
        QApplication.clipboard().setText('%s: %s\n\n%s' %
                (self.title, self.msg, self.det_msg))



def warning_dialog(parent, title, msg, det_msg='', show=False):
    d = MessageBox(QMessageBox.Warning, 'WARNING: '+title, msg, QMessageBox.Ok,
                    parent, det_msg)
    d.setEscapeButton(QMessageBox.Ok)
    d.setIconPixmap(QPixmap(I('dialog_warning.svg')))
    if show:
        return d.exec_()
    return d

def error_dialog(parent, title, msg, det_msg='', show=False,
        show_copy_button=True):
    d = MessageBox(QMessageBox.Critical, 'ERROR: '+title, msg, QMessageBox.Ok,
                    parent, det_msg)
    d.setIconPixmap(QPixmap(I('dialog_error.svg')))
    d.setEscapeButton(QMessageBox.Ok)
    if not show_copy_button:
        d.cb.setVisible(False)
    if show:
        return d.exec_()
    return d

def question_dialog(parent, title, msg, det_msg='', show_copy_button=True):
    d = MessageBox(QMessageBox.Question, title, msg, QMessageBox.Yes|QMessageBox.No,
                    parent, det_msg)
    d.setIconPixmap(QPixmap(I('dialog_information.svg')))
    d.setEscapeButton(QMessageBox.No)
    if not show_copy_button:
        d.cb.setVisible(False)

    return d.exec_() == QMessageBox.Yes

def info_dialog(parent, title, msg, det_msg='', show=False):
    d = MessageBox(QMessageBox.Information, title, msg, QMessageBox.Ok,
                    parent, det_msg)
    d.setIconPixmap(QPixmap(I('dialog_information.svg')))
    if show:
        return d.exec_()
    return d


def human_readable(size):
    """ Convert a size in bytes into a human readable form """
    divisor, suffix = 1, "B"
    if size < 1024*1024:
        divisor, suffix = 1024., "KB"
    elif size < 1024*1024*1024:
        divisor, suffix = 1024*1024, "MB"
    elif size < 1024*1024*1024*1024:
        divisor, suffix = 1024*1024*1024, "GB"
    size = str(float(size)/divisor)
    if size.find(".") > -1:
        size = size[:size.find(".")+2]
    if size.endswith('.0'):
        size = size[:-2]
    return size + " " + suffix

class Dispatcher(QObject):
    '''Convenience class to ensure that a function call always happens in the
    thread the reciver was created in.'''
    dispatch_signal = pyqtSignal(object, object)

    def __init__(self, func):
        QObject.__init__(self)
        self.func = func
        self.dispatch_signal.connect(self.dispatch, type=Qt.QueuedConnection)

    def __call__(self, *args, **kwargs):
        self.dispatch_signal.emit(args, kwargs)

    def dispatch(self, args, kwargs):
        self.func(*args, **kwargs)

class GetMetadata(QObject):
    '''
    Convenience class to ensure that metadata readers are used only in the
    GUI thread. Must be instantiated in the GUI thread.
    '''

    def __init__(self):
        QObject.__init__(self)
        self.connect(self, SIGNAL('edispatch(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                     self._get_metadata, Qt.QueuedConnection)
        self.connect(self, SIGNAL('idispatch(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                     self._from_formats, Qt.QueuedConnection)

    def __call__(self, id, *args, **kwargs):
        self.emit(SIGNAL('edispatch(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                  id, args, kwargs)

    def from_formats(self, id, *args, **kwargs):
        self.emit(SIGNAL('idispatch(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                  id, args, kwargs)

    def _from_formats(self, id, args, kwargs):
        try:
            mi = metadata_from_formats(*args, **kwargs)
        except:
            mi = MetaInformation('', [_('Unknown')])
        self.emit(SIGNAL('metadataf(PyQt_PyObject, PyQt_PyObject)'), id, mi)

    def _get_metadata(self, id, args, kwargs):
        try:
            mi = get_metadata(*args, **kwargs)
        except:
            mi = MetaInformation('', [_('Unknown')])
        self.emit(SIGNAL('metadata(PyQt_PyObject, PyQt_PyObject)'), id, mi)

class TableView(QTableView):

    def __init__(self, parent):
        QTableView.__init__(self, parent)
        self.read_settings()

    def read_settings(self):
        self.cw = dynamic[self.__class__.__name__+'column widths']

    def write_settings(self):
        dynamic[self.__class__.__name__+'column widths'] = \
         tuple([int(self.columnWidth(i)) for i in range(self.model().columnCount(None))])

    def restore_column_widths(self):
        if self.cw and len(self.cw):
            for i in range(len(self.cw)):
                self.setColumnWidth(i, self.cw[i])
            return True

class FileIconProvider(QFileIconProvider):

    ICONS = {
             'default' : 'unknown',
             'dir'     : 'dir',
             'zero'    : 'zero',

             'jpeg'    : 'jpeg',
             'jpg'     : 'jpeg',
             'gif'     : 'gif',
             'png'     : 'png',
             'bmp'     : 'bmp',
             'svg'     : 'svg',
             'html'    : 'html',
             'htm'     : 'html',
             'xhtml'   : 'html',
             'xhtm'    : 'html',
             'lit'     : 'lit',
             'lrf'     : 'lrf',
             'lrx'     : 'lrx',
             'pdf'     : 'pdf',
             'pdr'     : 'zero',
             'rar'     : 'rar',
             'zip'     : 'zip',
             'txt'     : 'txt',
             'prc'     : 'mobi',
             'azw'     : 'mobi',
             'mobi'    : 'mobi',
             'mbp'     : 'zero',
             'azw1'    : 'mobi',
             'tpz'     : 'mobi',
             'tan'     : 'zero',
             'epub'    : 'epub',
             'fb2'     : 'fb2',
             }

    def __init__(self):
        QFileIconProvider.__init__(self)
        self.icons = {}
        for key in self.__class__.ICONS.keys():
            self.icons[key] = I('mimetypes/')+self.__class__.ICONS[key]+'.svg'
        for i in ('dir', 'default', 'zero'):
            self.icons[i] = QIcon(self.icons[i])

    def key_from_ext(self, ext):
        key = ext if ext in self.icons.keys() else 'default'
        if key == 'default' and ext.count('.') > 0:
            ext = ext.rpartition('.')[2]
            key = ext if ext in self.icons.keys() else 'default'
        return key

    def cached_icon(self, key):
        candidate = self.icons[key]
        if isinstance(candidate, QIcon):
            return candidate
        icon = QIcon(candidate)
        self.icons[key] = icon
        return icon

    def icon_from_ext(self, ext):
        key = self.key_from_ext(ext.lower() if ext else '')
        return self.cached_icon(key)

    def load_icon(self, fileinfo):
        key = 'default'
        icons = self.icons
        if fileinfo.isSymLink():
            if not fileinfo.exists():
                return icons['zero']
            fileinfo = QFileInfo(fileinfo.readLink())
        if fileinfo.isDir():
            key = 'dir'
        else:
            ext = unicode(fileinfo.completeSuffix()).lower()
            key = self.key_from_ext(ext)
        return self.cached_icon(key)

    def icon(self, arg):
        if isinstance(arg, QFileInfo):
            return self.load_icon(arg)
        if arg == QFileIconProvider.Folder:
            return self.icons['dir']
        if arg == QFileIconProvider.File:
            return self.icons['default']
        return QFileIconProvider.icon(self, arg)

_file_icon_provider = None
def initialize_file_icon_provider():
    global _file_icon_provider
    if _file_icon_provider is None:
        _file_icon_provider = FileIconProvider()

def file_icon_provider():
    global _file_icon_provider
    initialize_file_icon_provider()
    return _file_icon_provider

class FileDialog(QObject):
    def __init__(self, title=_('Choose Files'),
                       filters=[],
                       add_all_files_filter=True,
                       parent=None,
                       modal = True,
                       name = '',
                       mode = QFileDialog.ExistingFiles,
                       ):
        QObject.__init__(self)
        ftext = ''
        if filters:
            for filter in filters:
                text, extensions = filter
                extensions = ['*'+(i if i.startswith('.') else '.'+i) for i in
                        extensions]
                ftext += '%s (%s);;'%(text, ' '.join(extensions))
        if add_all_files_filter or not ftext:
            ftext += 'All files (*)'
        if ftext.endswith(';;'):
            ftext = ftext[:-2]

        self.dialog_name = name if name else 'dialog_' + title
        self.selected_files = None
        self.fd = None

        initial_dir = dynamic.get(self.dialog_name, os.path.expanduser('~'))
        if not isinstance(initial_dir, basestring):
            initial_dir = os.path.expanduser('~')
        self.selected_files = []
        if mode == QFileDialog.AnyFile:
            f = unicode(QFileDialog.getSaveFileName(parent, title, initial_dir, ftext, ""))
            if f and os.path.exists(f):
                self.selected_files.append(f)
        elif mode == QFileDialog.ExistingFile:
            f = unicode(QFileDialog.getOpenFileName(parent, title, initial_dir, ftext, ""))
            if f and os.path.exists(f):
                self.selected_files.append(f)
        elif mode == QFileDialog.ExistingFiles:
            fs = QFileDialog.getOpenFileNames(parent, title, initial_dir, ftext, "")
            for f in fs:
                f = unicode(f)
                if f and os.path.exists(f):
                    self.selected_files.append(f)
        else:
            opts = QFileDialog.ShowDirsOnly if mode == QFileDialog.DirectoryOnly else QFileDialog.Option()
            f = unicode(QFileDialog.getExistingDirectory(parent, title, initial_dir, opts))
            if os.path.exists(f):
                self.selected_files.append(f)
        if self.selected_files:
            self.selected_files = [unicode(q) for q in self.selected_files]
            saved_loc = self.selected_files[0]
            if os.path.isfile(saved_loc):
                saved_loc = os.path.dirname(saved_loc)
            dynamic[self.dialog_name] = saved_loc
        self.accepted = bool(self.selected_files)

    def get_files(self):
        if self.selected_files is None:
            return tuple(os.path.abspath(unicode(i)) for i in self.fd.selectedFiles())
        return tuple(self.selected_files)


def choose_dir(window, name, title):
    fd = FileDialog(title, [], False, window, name=name,
                    mode=QFileDialog.DirectoryOnly)
    dir = fd.get_files()
    if dir:
        return dir[0]

def choose_files(window, name, title,
                 filters=[], all_files=True, select_only_single_file=False):
    '''
    Ask user to choose a bunch of files.
    @param name: Unique dialog name used to store the opened directory
    @param title: Title to show in dialogs titlebar
    @param filters: list of allowable extensions. Each element of the list
                     must be a 2-tuple with first element a string describing
                     the type of files to be filtered and second element a list
                     of extensions.
    @param all_files: If True add All files to filters.
    @param select_only_single_file: If True only one file can be selected
    '''
    mode = QFileDialog.ExistingFile if select_only_single_file else QFileDialog.ExistingFiles
    fd = FileDialog(title=title, name=name, filters=filters,
                    parent=window, add_all_files_filter=all_files, mode=mode,
                    )
    if fd.accepted:
        return fd.get_files()
    return None

def choose_images(window, name, title, select_only_single_file=True):
    mode = QFileDialog.ExistingFile if select_only_single_file else QFileDialog.ExistingFiles
    fd = FileDialog(title=title, name=name,
                    filters=[('Images', ['png', 'gif', 'jpeg', 'jpg', 'svg'])],
                    parent=window, add_all_files_filter=False, mode=mode,
                    )
    if fd.accepted:
        return fd.get_files()
    return None

def pixmap_to_data(pixmap, format='JPEG'):
    '''
    Return the QPixmap pixmap as a string saved in the specified format.
    '''
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    pixmap.save(buf, format)
    return str(ba.data())

class ResizableDialog(QDialog):

    def __init__(self, *args, **kwargs):
        QDialog.__init__(self, *args)
        self.setupUi(self)
        nh, nw = min_available_height()-25, available_width()-10
        if nh < 0:
            nh = 800
        if nw < 0:
            nw = 600
        nh = min(self.height(), nh)
        nw = min(self.width(), nw)
        self.resize(nw, nh)

gui_thread = None

qt_app = None
class Application(QApplication):

    def __init__(self, args):
        qargs = [i.encode('utf-8') if isinstance(i, unicode) else i for i in args]
        QApplication.__init__(self, qargs)
        self.file_event_hook = None
        global gui_thread, qt_app
        gui_thread = QThread.currentThread()
        self._translator = None
        self.load_translations()
        qt_app = self
        self._file_open_paths = []
        self._file_open_lock = RLock()

        if islinux:
            self.setStyleSheet('''
                    QToolTip {
                        border: 2px solid black;
                        padding: 5px;
                        border-radius: 10px;
                        opacity: 200;
                        background-color: #e1e1ff;
                    }
            ''')

    def _send_file_open_events(self):
        with self._file_open_lock:
            if self._file_open_paths:
                self.file_event_hook(self._file_open_paths)
                self._file_open_paths = []


    def load_translations(self):
        if self._translator is not None:
            self.removeTranslator(self._translator)
        self._translator = QTranslator(self)
        if set_qt_translator(self._translator):
            self.installTranslator(self._translator)

    def event(self, e):
        if callable(self.file_event_hook) and e.type() == QEvent.FileOpen:
            path = unicode(e.file())
            if os.access(path, os.R_OK):
                with self._file_open_lock:
                    self._file_open_paths.append(path)
                QTimer.singleShot(1000, self._send_file_open_events)
            return True
        else:
            return QApplication.event(self, e)

_store_app = None

def is_ok_to_use_qt():
    global gui_thread, _store_app
    if (islinux or isfreebsd) and ':' not in os.environ.get('DISPLAY', ''):
        return False
    if _store_app is None and QApplication.instance() is None:
        _store_app = QApplication([])
    if gui_thread is None:
        gui_thread = QThread.currentThread()
    return gui_thread is QThread.currentThread()

def is_gui_thread():
    global gui_thread
    return gui_thread is QThread.currentThread()


def find_forms(srcdir):
    base = os.path.join(srcdir, 'calibre', 'gui2')
    forms = []
    for root, _, files in os.walk(base):
        for name in files:
            if name.endswith('.ui'):
                forms.append(os.path.abspath(os.path.join(root, name)))

    return forms

def form_to_compiled_form(form):
    return form.rpartition('.')[0]+'_ui.py'

def build_forms(srcdir, info=None):
    import re, cStringIO
    from PyQt4.uic import compileUi
    forms = find_forms(srcdir)
    if info is None:
        from calibre import prints
        info = prints
    pat = re.compile(r'''(['"]):/images/([^'"]+)\1''')
    def sub(match):
        ans = 'I(%s%s%s)'%(match.group(1), match.group(2), match.group(1))
        return ans

    for form in forms:
        compiled_form = form_to_compiled_form(form)
        if not os.path.exists(compiled_form) or os.stat(form).st_mtime > os.stat(compiled_form).st_mtime:
            info('\tCompiling form', form)
            buf = cStringIO.StringIO()
            compileUi(form, buf)
            dat = buf.getvalue()
            dat = dat.replace('__appname__', 'calibre')
            dat = dat.replace('import images_rc', '')
            dat = dat.replace('from library import', 'from calibre.gui2.library import')
            dat = dat.replace('from widgets import', 'from calibre.gui2.widgets import')
            dat = dat.replace('from convert.xpath_wizard import',
                'from calibre.gui2.convert.xpath_wizard import')
            dat = re.compile(r'QtGui.QApplication.translate\(.+?,\s+"(.+?)(?<!\\)",.+?\)', re.DOTALL).sub(r'_("\1")', dat)
            dat = dat.replace('_("MMM yyyy")', '"MMM yyyy"')
            dat = pat.sub(sub, dat)

            if form.endswith('viewer%smain.ui'%os.sep):
                info('\t\tPromoting WebView')
                dat = dat.replace('self.view = QtWebKit.QWebView(', 'self.view = DocumentView(')
                dat = dat.replace('self.view = QWebView(', 'self.view = DocumentView(')
                dat = dat.replace('from QtWebKit.QWebView import QWebView',
                        'from PyQt4 import QtWebKit\nfrom PyQt4.QtWebKit import QWebView')
                dat += '\n\nfrom calibre.gui2.viewer.documentview import DocumentView'

            open(compiled_form, 'wb').write(dat)

_df = os.environ.get('CALIBRE_DEVELOP_FROM', None)
if _df and os.path.exists(_df):
    build_forms(_df)
