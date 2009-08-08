__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
""" The GUI """
import os
from PyQt4.QtCore import QVariant, QFileInfo, QObject, SIGNAL, QBuffer, Qt, QSize, \
                         QByteArray, QUrl, QTranslator, QCoreApplication, QThread
from PyQt4.QtGui import QFileDialog, QMessageBox, QPixmap, QFileIconProvider, \
                        QIcon, QTableView, QApplication, QDialog, QPushButton

ORG_NAME = 'KovidsBrain'
APP_UID  = 'libprs500'
from calibre import islinux, iswindows
from calibre.startup import get_lang
from calibre.utils.config import Config, ConfigProxy, dynamic
import calibre.resources as resources
from calibre.ebooks.metadata.meta import get_metadata, metadata_from_formats
from calibre.ebooks.metadata import MetaInformation


NONE = QVariant() #: Null value to return from the data function of item models

ALL_COLUMNS = ['title', 'authors', 'size', 'timestamp', 'rating', 'publisher',
        'tags', 'series', 'pubdate']

def _config():
    c = Config('gui', 'preferences for the calibre GUI')
    c.add_opt('frequently_used_directories', default=[],
              help=_('Frequently used directories'))
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
    c.add_opt('systray_icon', default=True, help=_('Show system tray icon'))
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

class MessageBox(QMessageBox):

    def __init__(self, type_, title, msg, buttons, parent, det_msg=''):
        QMessageBox.__init__(self, type_, title, msg, buttons, parent)
        self.title = title
        self.msg = msg
        self.det_msg = det_msg
        self.setDetailedText(det_msg)
        self.cb = QPushButton(_('Copy to Clipboard'))
        self.layout().addWidget(self.cb)
        self.connect(self.cb, SIGNAL('clicked()'), self.copy_to_clipboard)

    def copy_to_clipboard(self):
        QApplication.clipboard().setText('%s: %s\n\n%s' %
                (self.title, self.msg, self.det_msg))



def warning_dialog(parent, title, msg, det_msg='', show=False):
    d = MessageBox(QMessageBox.Warning, 'WARNING: '+title, msg, QMessageBox.Ok,
                    parent, det_msg)
    d.setIconPixmap(QPixmap(':/images/dialog_warning.svg'))
    if show:
        return d.exec_()
    return d

def error_dialog(parent, title, msg, det_msg='', show=False):
    d = MessageBox(QMessageBox.Critical, 'ERROR: '+title, msg, QMessageBox.Ok,
                    parent, det_msg)
    d.setIconPixmap(QPixmap(':/images/dialog_error.svg'))
    if show:
        return d.exec_()
    return d

def question_dialog(parent, title, msg, det_msg=''):
    d = MessageBox(QMessageBox.Question, title, msg, QMessageBox.Yes|QMessageBox.No,
                    parent, det_msg)
    d.setIconPixmap(QPixmap(':/images/dialog_information.svg'))
    return d.exec_() == QMessageBox.Yes

def info_dialog(parent, title, msg, det_msg='', show=False):
    d = MessageBox(QMessageBox.Information, title, msg, QMessageBox.NoButton,
                    parent, det_msg)
    d.setIconPixmap(QPixmap(':/images/dialog_information.svg'))
    if show:
        return d.exec_()
    return d


def qstring_to_unicode(q):
    return unicode(q)

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
    '''Convenience class to ensure that a function call always happens in the GUI thread'''
    SIGNAL = SIGNAL('dispatcher(PyQt_PyObject,PyQt_PyObject)')

    def __init__(self, func):
        QObject.__init__(self)
        self.func = func
        self.connect(self, self.SIGNAL, self.dispatch, Qt.QueuedConnection)

    def __call__(self, *args, **kwargs):
        self.emit(self.SIGNAL, args, kwargs)

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
             'rar'     : 'rar',
             'zip'     : 'zip',
             'txt'     : 'txt',
             'prc'     : 'mobi',
             'azw'     : 'mobi',
             'mobi'    : 'mobi',
             'epub'    : 'epub',
             }

    def __init__(self):
        QFileIconProvider.__init__(self)
        self.icons = {}
        for key in self.__class__.ICONS.keys():
            self.icons[key] = ':/images/mimetypes/'+self.__class__.ICONS[key]+'.svg'
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
            ext = qstring_to_unicode(fileinfo.completeSuffix()).lower()
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
    return _file_icon_provider

_sidebar_directories = []
def set_sidebar_directories(dirs):
    global _sidebar_directories
    if dirs is None:
        dirs = config['frequently_used_directories']
    _sidebar_directories = [QUrl.fromLocalFile(i) for i in dirs]

class FileDialog(QObject):
    def __init__(self, title='Choose Files',
                       filters=[],
                       add_all_files_filter=True,
                       parent=None,
                       modal = True,
                       name = '',
                       mode = QFileDialog.ExistingFiles,
                       ):
        QObject.__init__(self)
        initialize_file_icon_provider()
        ftext = ''
        if filters:
            for filter in filters:
                text, extensions = filter
                extensions = ['*.'+i if not i.startswith('.') else i for i in extensions]
                ftext += '%s (%s);;'%(text, ' '.join(extensions))
        if add_all_files_filter or not ftext:
            ftext += 'All files (*)'
        if ftext.endswith(';;'):
            ftext = ftext[:-2]

        self.dialog_name = name if name else 'dialog_' + title
        self.selected_files = None
        self.fd = None

        if islinux:
            self.fd = QFileDialog(parent)
            self.fd.setFileMode(mode)
            self.fd.setIconProvider(_file_icon_provider)
            self.fd.setModal(modal)
            self.fd.setNameFilter(ftext)
            self.fd.setWindowTitle(title)
            state = dynamic[self.dialog_name]
            if not state or not self.fd.restoreState(state):
                self.fd.setDirectory(os.path.expanduser('~'))
            osu = [i for i in self.fd.sidebarUrls()]
            self.fd.setSidebarUrls(osu + _sidebar_directories)
            QObject.connect(self.fd, SIGNAL('accepted()'), self.save_dir)
            self.accepted = self.fd.exec_() == QFileDialog.Accepted
        else:
            dir = dynamic.get(self.dialog_name, os.path.expanduser('~'))
            self.selected_files = []
            if mode == QFileDialog.AnyFile:
                f = qstring_to_unicode(
                    QFileDialog.getSaveFileName(parent, title, dir, ftext, ""))
                if os.path.exists(f):
                    self.selected_files.append(f)
            elif mode == QFileDialog.ExistingFile:
                f = qstring_to_unicode(
                    QFileDialog.getOpenFileName(parent, title, dir, ftext, ""))
                if os.path.exists(f):
                    self.selected_files.append(f)
            elif mode == QFileDialog.ExistingFiles:
                fs = QFileDialog.getOpenFileNames(parent, title, dir, ftext, "")
                for f in fs:
                    if os.path.exists(qstring_to_unicode(f)):
                        self.selected_files.append(f)
            else:
                opts = QFileDialog.ShowDirsOnly if mode == QFileDialog.DirectoryOnly else QFileDialog.Option()
                f = qstring_to_unicode(
                        QFileDialog.getExistingDirectory(parent, title, dir, opts))
                if os.path.exists(f):
                    self.selected_files.append(f)
            if self.selected_files:
                self.selected_files = [qstring_to_unicode(q) for q in self.selected_files]
                dynamic[self.dialog_name] =  os.path.dirname(self.selected_files[0])
            self.accepted = bool(self.selected_files)



    def get_files(self):
        if islinux and self.fd.result() != self.fd.Accepted:
            return tuple()
        if self.selected_files is None:
            return tuple(os.path.abspath(qstring_to_unicode(i)) for i in self.fd.selectedFiles())
        return tuple(self.selected_files)

    def save_dir(self):
        if self.fd:
            dynamic[self.dialog_name] =  self.fd.saveState()


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

class Application(QApplication):

    def __init__(self, args):
        qargs = [i.encode('utf-8') if isinstance(i, unicode) else i for i in args]
        QApplication.__init__(self, qargs)
        global gui_thread
        gui_thread = QThread.currentThread()
        self.translator = QTranslator(self)
        lang = get_lang()
        if lang:
            data = getattr(resources, 'qt_'+lang, None)
            if data:
                self.translator.loadFromData(data)
                self.installTranslator(self.translator)

def is_ok_to_use_qt():
    global gui_thread
    if islinux and os.environ.get('DISPLAY', None) is None:
        return False
    if QApplication.instance() is None:
        QApplication([])
    if gui_thread is None:
        gui_thread = QThread.currentThread()
    return gui_thread is QThread.currentThread()

