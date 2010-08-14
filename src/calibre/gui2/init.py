#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import functools, sys, os

from PyQt4.Qt import Qt, QStackedWidget, QMenu, \
        QSize, QSizePolicy, QStatusBar, QLabel, QFont

from calibre.utils.config import prefs
from calibre.constants import isosx, __appname__, preferred_encoding, \
    __version__
from calibre.gui2 import config, is_widescreen
from calibre.gui2.library.views import BooksView, DeviceBooksView
from calibre.gui2.widgets import Splitter
from calibre.gui2.tag_view import TagBrowserWidget
from calibre.gui2.book_details import BookDetails
from calibre.gui2.notify import get_notifier

_keep_refs = []

def partial(*args, **kwargs):
    ans = functools.partial(*args, **kwargs)
    _keep_refs.append(ans)
    return ans

LIBRARY_CONTEXT_MENU = (
        'Edit Metadata', 'Send To Device', 'Save To Disk', 'Connect Share', None,
        'Convert Books', 'View', 'Open Folder', 'Show Book Details', None,
        'Remove Books',
        )

DEVICE_CONTEXT_MENU = ('View', 'Save To Disk', None, 'Remove Books', None,
                       'Add To Library', 'Edit Collections',
        )

class LibraryViewMixin(object): # {{{

    def __init__(self, db):
        lm = QMenu(self)
        def populate_menu(m, items):
            for what in items:
                if what is None:
                    lm.addSeparator()
                elif what in self.iactions:
                    lm.addAction(self.iactions[what].qaction)
        populate_menu(lm, LIBRARY_CONTEXT_MENU)
        dm = QMenu(self)
        populate_menu(dm, DEVICE_CONTEXT_MENU)
        self.library_view.set_context_menu(lm)
        for v in (self.memory_view, self.card_a_view, self.card_b_view):
            v.set_context_menu(dm)

        self.library_view.files_dropped.connect(self.iactions['Add Books'].files_dropped, type=Qt.QueuedConnection)
        for func, args in [
                             ('connect_to_search_box', (self.search,
                                 self.search_done)),
                             ('connect_to_book_display',
                                 (self.book_details.show_data,)),
                             ]:
            for view in (self.library_view, self.memory_view, self.card_a_view, self.card_b_view):
                getattr(view, func)(*args)

        self.memory_view.connect_dirtied_signal(self.upload_booklists)
        self.memory_view.connect_upload_collections_signal(
                                    func=self.upload_collections, oncard=None)
        self.card_a_view.connect_dirtied_signal(self.upload_booklists)
        self.card_a_view.connect_upload_collections_signal(
                                    func=self.upload_collections, oncard='carda')
        self.card_b_view.connect_dirtied_signal(self.upload_booklists)
        self.card_b_view.connect_upload_collections_signal(
                                    func=self.upload_collections, oncard='cardb')
        self.book_on_device(None, reset=True)
        db.set_book_on_device_func(self.book_on_device)
        self.library_view.set_database(db)
        self.library_view.model().set_book_on_device_func(self.book_on_device)
        prefs['library_path'] = self.library_path

        for view in ('library', 'memory', 'card_a', 'card_b'):
            view = getattr(self, view+'_view')
            view.verticalHeader().sectionDoubleClicked.connect(self.iactions['View'].view_specific_book)



    def search_done(self, view, ok):
        if view is self.current_view():
            self.search.search_done(ok)
            self.set_number_of_books_shown()

    # }}}

class LibraryWidget(Splitter): # {{{

    def __init__(self, parent):
        orientation = Qt.Vertical
        if config['gui_layout'] == 'narrow':
            orientation = Qt.Horizontal if is_widescreen() else Qt.Vertical
        idx = 0 if orientation == Qt.Vertical else 1
        size = 300 if orientation == Qt.Vertical else 550
        Splitter.__init__(self, 'cover_browser_splitter', _('Cover Browser'),
                I('cover_flow.svg'),
                orientation=orientation, parent=parent,
                connect_button=not config['separate_cover_flow'],
                side_index=idx, initial_side_size=size, initial_show=False,
                shortcut=_('Shift+Alt+B'))
        parent.library_view = BooksView(parent)
        parent.library_view.setObjectName('library_view')
        self.addWidget(parent.library_view)
# }}}

class Stack(QStackedWidget): # {{{

    def __init__(self, parent):
        QStackedWidget.__init__(self, parent)

        parent.cb_splitter = LibraryWidget(parent)
        self.tb_widget = TagBrowserWidget(parent)
        parent.tb_splitter = Splitter('tag_browser_splitter',
                _('Tag Browser'), I('tags.svg'),
                parent=parent, side_index=0, initial_side_size=200,
                shortcut=_('Shift+Alt+T'))
        parent.tb_splitter.addWidget(self.tb_widget)
        parent.tb_splitter.addWidget(parent.cb_splitter)
        parent.tb_splitter.setCollapsible(parent.tb_splitter.other_index, False)

        self.addWidget(parent.tb_splitter)
        for x in ('memory', 'card_a', 'card_b'):
            name = x+'_view'
            w = DeviceBooksView(parent)
            setattr(parent, name, w)
            self.addWidget(w)
            w.setObjectName(name)


# }}}

class StatusBar(QStatusBar): # {{{

    def __init__(self, parent=None):
        QStatusBar.__init__(self, parent)
        self.default_message = __appname__ + ' ' + _('version') + ' ' + \
                self.get_version() + ' ' + _('created by Kovid Goyal')
        self.device_string = ''
        self.update_label = QLabel('')
        self.update_label.setOpenExternalLinks(True)
        self.addPermanentWidget(self.update_label)
        self.update_label.setVisible(False)
        self._font = QFont()
        self._font.setBold(True)
        self.setFont(self._font)

    def initialize(self, systray=None):
        self.systray = systray
        self.notifier = get_notifier(systray)
        self.messageChanged.connect(self.message_changed,
                type=Qt.QueuedConnection)
        self.message_changed('')

    def device_connected(self, devname):
        self.device_string = _('Connected ') + devname
        self.clearMessage()

    def device_disconnected(self):
        self.device_string = ''
        self.clearMessage()

    def new_version_available(self, ver, url):
        msg = (u'<span style="color:red; font-weight: bold">%s: <a href="%s">%s<a></span>') % (
                _('Update found'), url, ver)
        self.update_label.setText(msg)
        self.update_label.setCursor(Qt.PointingHandCursor)
        self.update_label.setVisible(True)

    def get_version(self):
        dv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
        v = __version__
        if getattr(sys, 'frozen', False) and dv and os.path.abspath(dv) in sys.path:
            v += '*'
        return v

    def show_message(self, msg, timeout=0):
        self.showMessage(msg, timeout)
        if self.notifier is not None and not config['disable_tray_notification']:
            if isosx and isinstance(msg, unicode):
                try:
                    msg = msg.encode(preferred_encoding)
                except UnicodeEncodeError:
                    msg = msg.encode('utf-8')
            self.notifier(msg)

    def clear_message(self):
        self.clearMessage()

    def message_changed(self, msg):
        if not msg or msg.isEmpty() or msg.isNull() or \
                not unicode(msg).strip():
            extra = ''
            if self.device_string:
                extra = ' ..::.. ' + self.device_string
            self.showMessage(self.default_message + extra)


# }}}

class LayoutMixin(object): # {{{

    def __init__(self):

        if config['gui_layout'] == 'narrow': # narrow {{{
            self.book_details = BookDetails(False, self)
            self.stack = Stack(self)
            self.bd_splitter = Splitter('book_details_splitter',
                    _('Book Details'), I('book.svg'),
                    orientation=Qt.Vertical, parent=self, side_index=1,
                    shortcut=_('Alt+D'))
            self.bd_splitter.addWidget(self.stack)
            self.bd_splitter.addWidget(self.book_details)
            self.bd_splitter.setCollapsible(self.bd_splitter.other_index, False)
            self.centralwidget.layout().addWidget(self.bd_splitter)
            # }}}
        else: # wide {{{
            self.bd_splitter = Splitter('book_details_splitter',
                    _('Book Details'), I('book.svg'), initial_side_size=200,
                    orientation=Qt.Horizontal, parent=self, side_index=1,
                    shortcut=_('Shift+Alt+D'))
            self.stack = Stack(self)
            self.bd_splitter.addWidget(self.stack)
            self.book_details = BookDetails(True, self)
            self.bd_splitter.addWidget(self.book_details)
            self.bd_splitter.setCollapsible(self.bd_splitter.other_index, False)
            self.bd_splitter.setSizePolicy(QSizePolicy(QSizePolicy.Expanding,
                QSizePolicy.Expanding))
            self.centralwidget.layout().addWidget(self.bd_splitter)
        # }}}

        self.status_bar = StatusBar(self)
        for x in ('cb', 'tb', 'bd'):
            button = getattr(self, x+'_splitter').button
            button.setIconSize(QSize(24, 24))
            self.status_bar.addPermanentWidget(button)
        self.status_bar.addPermanentWidget(self.jobs_button)
        self.setStatusBar(self.status_bar)

    def finalize_layout(self):
        self.status_bar.initialize(self.system_tray_icon)
        self.book_details.show_book_info.connect(self.iactions['Show Book Details'].show_book_info)
        self.book_details.files_dropped.connect(self.iactions['Add Books'].files_dropped_on_book)
        self.book_details.open_containing_folder.connect(self.iactions['View'].view_folder_for_id)
        self.book_details.view_specific_format.connect(self.iactions['View'].view_format_by_id)

        m = self.library_view.model()
        if m.rowCount(None) > 0:
            self.library_view.set_current_row(0)
            m.current_changed(self.library_view.currentIndex(),
                    self.library_view.currentIndex())
        self.library_view.setFocus(Qt.OtherFocusReason)


    def save_layout_state(self):
        for x in ('library', 'memory', 'card_a', 'card_b'):
            getattr(self, x+'_view').save_state()

        for x in ('cb', 'tb', 'bd'):
            getattr(self, x+'_splitter').save_state()

    def read_layout_settings(self):
        # View states are restored automatically when set_database is called

        for x in ('cb', 'tb', 'bd'):
            getattr(self, x+'_splitter').restore_state()

# }}}

