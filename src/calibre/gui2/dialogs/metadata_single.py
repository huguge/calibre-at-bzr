__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
The dialog used to edit meta information for a book as well as
add/remove formats
'''

import os, re, time, traceback, textwrap
from functools import partial
from threading import Thread

from PyQt4.Qt import SIGNAL, QObject, Qt, QTimer, QDate, \
    QPixmap, QListWidgetItem, QDialog, pyqtSignal, QMessageBox, QIcon, \
    QPushButton

from calibre.gui2 import error_dialog, file_icon_provider, dynamic, \
                           choose_files, choose_images, ResizableDialog, \
                           warning_dialog, question_dialog
from calibre.gui2.dialogs.metadata_single_ui import Ui_MetadataSingleDialog
from calibre.gui2.dialogs.fetch_metadata import FetchMetadata
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.gui2.widgets import ProgressIndicator
from calibre.ebooks import BOOK_EXTENSIONS
from calibre.ebooks.metadata import string_to_authors, \
        authors_to_string, check_isbn, title_sort
from calibre.ebooks.metadata.covers import download_cover
from calibre.ebooks.metadata.meta import get_metadata
from calibre.ebooks.metadata import MetaInformation
from calibre.utils.config import prefs, tweaks
from calibre.utils.date import qt_to_dt, local_tz, utcfromtimestamp
from calibre.utils.icu import sort_key
from calibre.customize.ui import run_plugins_on_import, get_isbndb_key
from calibre.gui2.preferences.social import SocialMetadata
from calibre.gui2.custom_column_widgets import populate_metadata_page
from calibre import strftime
from calibre.library.comments import comments_to_html

class CoverFetcher(Thread): # {{{

    def __init__(self, username, password, isbn, timeout, title, author):
        Thread.__init__(self)
        self.daemon = True

        self.username = username.strip() if username else username
        self.password = password.strip() if password else password
        self.timeout = timeout
        self.isbn = isbn
        self.title = title
        self.needs_isbn = False
        self.author = author
        self.exception = self.traceback = self.cover_data = self.errors = None

    def run(self):
        try:
            au = self.author if self.author else None
            mi = MetaInformation(self.title, [au])
            if not self.isbn:
                from calibre.ebooks.metadata.fetch import search
                if not self.title:
                    self.needs_isbn = True
                    return
                key = get_isbndb_key()
                if not key:
                    key = None
                results = search(title=self.title, author=au,
                        isbndb_key=key)[0]
                results = sorted([x.isbn for x in results if x.isbn],
                        cmp=lambda x,y:cmp(len(x),len(y)), reverse=True)
                if not results:
                    self.needs_isbn = True
                    return
                self.isbn = results[0]

            mi.isbn = self.isbn

            self.cover_data, self.errors = download_cover(mi,
                    timeout=self.timeout)
        except Exception, e:
            self.exception = e
            self.traceback = traceback.format_exc()
            print self.traceback

# }}}

class Format(QListWidgetItem): # {{{

    def __init__(self, parent, ext, size, path=None, timestamp=None):
        self.path = path
        self.ext = ext
        self.size = float(size)/(1024*1024)
        text = '%s (%.2f MB)'%(self.ext.upper(), self.size)
        QListWidgetItem.__init__(self, file_icon_provider().icon_from_ext(ext),
                                 text, parent, QListWidgetItem.UserType)
        if timestamp is not None:
            ts = timestamp.astimezone(local_tz)
            t = strftime('%a, %d %b %Y [%H:%M:%S]', ts.timetuple())
            text = _('Last modified: %s')%t
            self.setToolTip(text)
            self.setStatusTip(text)

# }}}


class MetadataSingleDialog(ResizableDialog, Ui_MetadataSingleDialog):

    COVER_FETCH_TIMEOUT = 240 # seconds
    view_format = pyqtSignal(object)

    # Cover processing {{{

    def set_cover(self):
        mi, ext = self.get_selected_format_metadata()
        if mi is None:
            return
        cdata = None
        if mi.cover and os.access(mi.cover, os.R_OK):
            cdata = open(mi.cover).read()
        elif mi.cover_data[1] is not None:
            cdata = mi.cover_data[1]
        if cdata is None:
            error_dialog(self, _('Could not read cover'),
                         _('Could not read cover from %s format')%ext).exec_()
            return
        pix = QPixmap()
        pix.loadFromData(cdata)
        if pix.isNull():
            error_dialog(self, _('Could not read cover'),
                         _('The cover in the %s format is invalid')%ext).exec_()
            return
        self.cover.setPixmap(pix)
        self.update_cover_tooltip()
        self.cover_changed = True
        self.cpixmap = pix
        self.cover_data = cdata

    def trim_cover(self, *args):
        from calibre.utils.magick import Image
        cdata = self.cover_data
        if not cdata:
            return
        im = Image()
        im.load(cdata)
        im.trim(10)
        cdata = im.export('png')
        pix = QPixmap()
        pix.loadFromData(cdata)
        self.cover.setPixmap(pix)
        self.update_cover_tooltip()
        self.cover_changed = True
        self.cpixmap = pix
        self.cover_data = cdata



    def update_cover_tooltip(self):
        p = self.cover.pixmap()
        self.cover.setToolTip(_('Cover size: %dx%d pixels') %
                (p.width(), p.height()))


    def do_reset_cover(self, *args):
        pix = QPixmap(I('default_cover.png'))
        self.cover.setPixmap(pix)
        self.update_cover_tooltip()
        self.cover_changed = True
        self.cover_data = None

    def select_cover(self, checked):
        files = choose_images(self, 'change cover dialog',
                             _('Choose cover for ') + unicode(self.title.text()))
        if not files:
            return
        _file = files[0]
        if _file:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                d = error_dialog(self, _('Cannot read'),
                        _('You do not have permission to read the file: ') + _file)
                d.exec_()
                return
            cf, cover = None, None
            try:
                cf = open(_file, "rb")
                cover = cf.read()
            except IOError, e:
                d = error_dialog(self, _('Error reading file'),
                        _("<p>There was an error reading from file: <br /><b>") + _file + "</b></p><br />"+str(e))
                d.exec_()
            if cover:
                pix = QPixmap()
                pix.loadFromData(cover)
                if pix.isNull():
                    d = error_dialog(self,
                        _("Not a valid picture"),
                            _file + _(" is not a valid picture"))
                    d.exec_()
                else:
                    self.cover.setPixmap(pix)
                    self.update_cover_tooltip()
                    self.cover_changed = True
                    self.cpixmap = pix
                    self.cover_data = cover

    def generate_cover(self, *args):
        from calibre.ebooks import calibre_cover
        from calibre.ebooks.metadata import fmt_sidx
        from calibre.gui2 import config
        title = unicode(self.title.text()).strip()
        author = unicode(self.authors.text()).strip()
        if not title or not author:
            return error_dialog(self, _('Specify title and author'),
                    _('You must specify a title and author before generating '
                        'a cover'), show=True)
        series = unicode(self.series.text()).strip()
        series_string = None
        if series:
            series_string = _('Book %s of %s')%(
                    fmt_sidx(self.series_index.value(),
                        use_roman=config['use_roman_numerals_for_series_number']), series)
        self.cover_data = calibre_cover(title, author,
                series_string=series_string)
        pix = QPixmap()
        pix.loadFromData(self.cover_data)
        self.cover.setPixmap(pix)
        self.update_cover_tooltip()
        self.cover_changed = True
        self.cpixmap = pix

    def cover_dropped(self, cover_data):
        self.cover_changed = True
        self.cover_data = cover_data
        self.update_cover_tooltip()

    def fetch_cover(self):
        isbn   = re.sub(r'[^0-9a-zA-Z]', '', unicode(self.isbn.text())).strip()
        self.fetch_cover_button.setEnabled(False)
        self.setCursor(Qt.WaitCursor)
        title, author = map(unicode, (self.title.text(), self.authors.text()))
        self.cover_fetcher = CoverFetcher(None, None, isbn,
                                            self.timeout, title, author)
        self.cover_fetcher.start()
        self.cf_start_time = time.time()
        self.pi.start(_('Downloading cover...'))
        QTimer.singleShot(100, self.hangcheck)

    def hangcheck(self):
        cf = self.cover_fetcher
        if cf is None:
            # Called after dialog closed
            return

        if cf.is_alive() and \
            time.time()-self.cf_start_time < self.COVER_FETCH_TIMEOUT:
            QTimer.singleShot(100, self.hangcheck)
            return

        try:
            if cf.is_alive():
                error_dialog(self, _('Cannot fetch cover'),
                    _('<b>Could not fetch cover.</b><br/>')+
                    _('The download timed out.')).exec_()
                return
            if cf.needs_isbn:
                error_dialog(self, _('Cannot fetch cover'),
                    _('Could not find cover for this book. Try '
                      'specifying the ISBN first.')).exec_()
                return
            if cf.exception is not None:
                err = cf.exception
                error_dialog(self, _('Cannot fetch cover'),
                    _('<b>Could not fetch cover.</b><br/>')+unicode(err)).exec_()
                return
            if cf.errors and cf.cover_data is None:
                details = u'\n\n'.join([e[-1] + ': ' + e[1] for e in cf.errors])
                error_dialog(self, _('Cannot fetch cover'),
                    _('<b>Could not fetch cover.</b><br/>') +
                    _('For the error message from each cover source, '
                      'click Show details below.'), det_msg=details, show=True)
                return

            pix = QPixmap()
            pix.loadFromData(cf.cover_data)
            if pix.isNull():
                error_dialog(self, _('Bad cover'),
                             _('The cover is not a valid picture')).exec_()
            else:
                self.cover.setPixmap(pix)
                self.update_cover_tooltip()
                self.cover_changed = True
                self.cpixmap = pix
                self.cover_data = cf.cover_data
        finally:
            self.fetch_cover_button.setEnabled(True)
            self.unsetCursor()
            if self.pi is not None:
                self.pi.stop()


    # }}}

    # Formats processing {{{
    def add_format(self, x):
        files = choose_files(self, 'add formats dialog',
                             _("Choose formats for ") + unicode((self.title.text())),
                             [(_('Books'), BOOK_EXTENSIONS)])
        self._add_formats(files)

    def _add_formats(self, paths):
        added = False
        if not paths:
            return added
        bad_perms = []
        for _file in paths:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                bad_perms.append(_file)
                continue

            nfile = run_plugins_on_import(_file)
            if nfile is not None:
                _file = nfile
            stat = os.stat(_file)
            size = stat.st_size
            ext = os.path.splitext(_file)[1].lower().replace('.', '')
            timestamp = utcfromtimestamp(stat.st_mtime)
            for row in range(self.formats.count()):
                fmt = self.formats.item(row)
                if fmt.ext.lower() == ext:
                    self.formats.takeItem(row)
                    break
            Format(self.formats, ext, size, path=_file, timestamp=timestamp)
            self.formats_changed = True
            added = True
        if bad_perms:
            error_dialog(self, _('No permission'),
                    _('You do not have '
                'permission to read the following files:'),
                det_msg='\n'.join(bad_perms), show=True)

        return added

    def formats_dropped(self, event, paths):
        if self._add_formats(paths):
            event.accept()

    def remove_format(self, *args):
        rows = self.formats.selectionModel().selectedRows(0)
        for row in rows:
            self.formats.takeItem(row.row())
            self.formats_changed = True

    def get_selected_format_metadata(self):
        old = prefs['read_file_metadata']
        if not old:
            prefs['read_file_metadata'] = True
        try:
            row = self.formats.currentRow()
            fmt = self.formats.item(row)
            if fmt is None:
                if self.formats.count() == 1:
                    fmt = self.formats.item(0)
                if fmt is None:
                    error_dialog(self, _('No format selected'),
                        _('No format selected')).exec_()
                    return None, None
            ext = fmt.ext.lower()
            if fmt.path is None:
                stream = self.db.format(self.row, ext, as_file=True)
            else:
                stream = open(fmt.path, 'r+b')
            try:
                mi = get_metadata(stream, ext)
                return mi, ext
            except:
                error_dialog(self, _('Could not read metadata'),
                            _('Could not read metadata from %s format')%ext).exec_()
            return None, None
        finally:
            if old != prefs['read_file_metadata']:
                prefs['read_file_metadata'] = old

    def set_metadata_from_format(self):
        mi, ext = self.get_selected_format_metadata()
        if mi is None:
            return
        if mi.title:
            self.title.setText(mi.title)
        if mi.authors:
            self.authors.setEditText(authors_to_string(mi.authors))
        if mi.author_sort:
            self.author_sort.setText(mi.author_sort)
        if mi.rating is not None:
            try:
                self.rating.setValue(mi.rating)
            except:
                pass
        if mi.publisher:
            self.publisher.setEditText(mi.publisher)
        if mi.tags:
            self.tags.setText(', '.join(mi.tags))
        if mi.isbn:
            self.isbn.setText(mi.isbn)
        if mi.pubdate:
            self.pubdate.setDate(QDate(mi.pubdate.year, mi.pubdate.month,
                mi.pubdate.day))
        if mi.series and mi.series.strip():
            self.series.setEditText(mi.series)
            if mi.series_index is not None:
                self.series_index.setValue(float(mi.series_index))
        if mi.comments and mi.comments.strip():
            comments = comments_to_html(mi.comments)
            self.comments.html = comments


    def sync_formats(self):
        old_extensions, new_extensions, paths = set(), set(), {}
        for row in range(self.formats.count()):
            fmt = self.formats.item(row)
            ext, path = fmt.ext.lower(), fmt.path
            if 'unknown' in ext.lower():
                ext = None
            if path:
                new_extensions.add(ext)
                paths[ext] = path
            else:
                old_extensions.add(ext)
        for ext in new_extensions:
            self.db.add_format(self.row, ext, open(paths[ext], 'rb'), notify=False)
        db_extensions = set([f.lower() for f in self.db.formats(self.row).split(',')])
        extensions = new_extensions.union(old_extensions)
        for ext in db_extensions:
            if ext not in extensions:
                self.db.remove_format(self.row, ext, notify=False)

    def show_format(self, item, *args):
        fmt = item.ext
        self.view_format.emit(fmt)

    # }}}

    def __init__(self, window, row, db, prev=None,
            next_=None):
        ResizableDialog.__init__(self, window)
        self.cover_fetcher = None
        self.bc_box.layout().setAlignment(self.cover, Qt.AlignCenter|Qt.AlignHCenter)
        base = unicode(self.author_sort.toolTip())
        ok_tooltip = '<p>' + textwrap.fill(base+'<br><br>'+
                            _(' The green color indicates that the current '
                    'author sort matches the current author'))
        bad_tooltip = '<p>'+textwrap.fill(base + '<br><br>'+
                _(' The red color indicates that the current '
                    'author sort does not match the current author. '
                    'No action is required if this is what you want.'))
        self.aus_tooltips = (ok_tooltip, bad_tooltip)

        base = unicode(self.title_sort.toolTip())
        ok_tooltip = '<p>' + textwrap.fill(base+'<br><br>'+
                            _(' The green color indicates that the current '
                              'title sort matches the current title'))
        bad_tooltip = '<p>'+textwrap.fill(base + '<br><br>'+
                _(' The red color warns that the current '
                  'title sort does not match the current title. '
                  'No action is required if this is what you want.'))
        self.ts_tooltips = (ok_tooltip, bad_tooltip)
        self.row_delta = 0
        if prev:
            self.prev_button = QPushButton(QIcon(I('back.png')), _('Previous'),
                    self)
            self.button_box.addButton(self.prev_button, self.button_box.ActionRole)
            tip = _('Save changes and edit the metadata of %s')%prev
            self.prev_button.setToolTip(tip)
            self.prev_button.clicked.connect(partial(self.next_triggered,
                -1))
        if next_:
            self.next_button = QPushButton(QIcon(I('forward.png')), _('Next'),
                    self)
            self.button_box.addButton(self.next_button, self.button_box.ActionRole)
            tip = _('Save changes and edit the metadata of %s')%next_
            self.next_button.setToolTip(tip)
            self.next_button.clicked.connect(partial(self.next_triggered, 1))

        self.splitter.setStretchFactor(100, 1)
        self.read_state()
        self.db = db
        self.pi = ProgressIndicator(self)
        self.id = db.id(row)
        self.row = row
        self.cover_data = None
        self.formats_changed = False
        self.formats.setAcceptDrops(True)
        self.cover_changed = False
        self.cpixmap = None
        self.pubdate.setMinimumDate(QDate(100,1,1))
        pubdate_format = tweaks['gui_pubdate_display_format']
        if pubdate_format is not None:
            self.pubdate.setDisplayFormat(pubdate_format)
        self.date.setMinimumDate(QDate(100,1,1))

        self.connect(self.cover, SIGNAL('cover_changed(PyQt_PyObject)'), self.cover_dropped)
        QObject.connect(self.cover_button, SIGNAL("clicked(bool)"), \
                                                    self.select_cover)
        QObject.connect(self.add_format_button, SIGNAL("clicked(bool)"), \
                                                    self.add_format)
        self.connect(self.formats,
                SIGNAL('formats_dropped(PyQt_PyObject,PyQt_PyObject)'),
                self.formats_dropped)
        QObject.connect(self.remove_format_button, SIGNAL("clicked(bool)"), \
                                                self.remove_format)
        QObject.connect(self.fetch_metadata_button, SIGNAL('clicked()'),
                        self.fetch_metadata)

        QObject.connect(self.fetch_cover_button, SIGNAL('clicked()'),
                        self.fetch_cover)
        QObject.connect(self.tag_editor_button, SIGNAL('clicked()'),
                        self.edit_tags)
        QObject.connect(self.remove_series_button, SIGNAL('clicked()'),
                        self.remove_unused_series)
        QObject.connect(self.auto_author_sort, SIGNAL('clicked()'),
                        self.deduce_author_sort)
        QObject.connect(self.auto_title_sort, SIGNAL('clicked()'),
                        self.deduce_title_sort)
        self.trim_cover_button.clicked.connect(self.trim_cover)
        self.connect(self.title_sort, SIGNAL('textChanged(const QString&)'),
                     self.title_sort_box_changed)
        self.connect(self.title, SIGNAL('textChanged(const QString&)'),
                     self.title_box_changed)
        self.connect(self.author_sort, SIGNAL('textChanged(const QString&)'),
                     self.author_sort_box_changed)
        self.connect(self.authors, SIGNAL('editTextChanged(const QString&)'),
                     self.authors_box_changed)
        self.connect(self.formats, SIGNAL('itemDoubleClicked(QListWidgetItem*)'),
                self.show_format)
        self.connect(self.formats, SIGNAL('delete_format()'), self.remove_format)
        self.connect(self.button_set_cover, SIGNAL('clicked()'), self.set_cover)
        self.connect(self.button_set_metadata, SIGNAL('clicked()'),
                self.set_metadata_from_format)
        self.connect(self.reset_cover, SIGNAL('clicked()'), self.do_reset_cover)
        self.connect(self.swap_button, SIGNAL('clicked()'), self.swap_title_author)
        self.timeout = float(prefs['network_timeout'])


        self.title.setText(db.title(row))
        self.title_sort.setText(db.title_sort(row))
        isbn = db.isbn(self.id, index_is_id=True)
        if not isbn:
            isbn = ''
        self.isbn.textChanged.connect(self.validate_isbn)
        self.isbn.setText(isbn)
        aus = self.db.author_sort(row)
        self.author_sort.setText(aus if aus else '')
        tags = self.db.tags(row)
        self.original_tags = ', '.join(tags.split(',')) if tags else ''
        self.tags.setText(self.original_tags)
        self.tags.update_tags_cache(self.db.all_tags())
        rating = self.db.rating(row)
        if rating > 0:
            self.rating.setValue(int(rating/2.))
        comments = self.db.comments(row)
        if comments and comments.strip():
            comments = comments_to_html(comments)
            self.comments.html = comments
        cover = self.db.cover(row)
        pubdate = db.pubdate(self.id, index_is_id=True)
        self.pubdate.setDate(QDate(pubdate.year, pubdate.month,
            pubdate.day))
        timestamp = db.timestamp(self.id, index_is_id=True)
        self.date.setDate(QDate(timestamp.year, timestamp.month,
            timestamp.day))
        self.orig_date = qt_to_dt(self.date.date())

        exts = self.db.formats(row)
        if exts:
            exts = exts.split(',')
            for ext in exts:
                if not ext:
                    ext = ''
                size = self.db.sizeof_format(row, ext)
                timestamp = self.db.format_last_modified(self.id, ext)
                if size is None:
                    continue
                Format(self.formats, ext, size, timestamp=timestamp)


        self.initialize_combos()
        si = self.db.series_index(row)
        if si is None:
            si = 1.0
        try:
            self.series_index.setValue(float(si))
        except:
            self.series_index.setValue(1.0)
        QObject.connect(self.series, SIGNAL('currentIndexChanged(int)'), self.enable_series_index)
        QObject.connect(self.series, SIGNAL('editTextChanged(QString)'), self.enable_series_index)
        self.series.lineEdit().editingFinished.connect(self.increment_series_index)

        pm = QPixmap()
        if cover:
            pm.loadFromData(cover)
        if pm.isNull():
            pm = QPixmap(I('default_cover.png'))
        else:
            self.cover_data = cover
        self.cover.setPixmap(pm)
        self.update_cover_tooltip()
        self.original_series_name = unicode(self.series.text()).strip()
        if len(db.custom_column_label_map) == 0:
            self.central_widget.tabBar().setVisible(False)
        else:
            self.create_custom_column_editors()
        self.generate_cover_button.clicked.connect(self.generate_cover)

        self.original_author = unicode(self.authors.text()).strip()
        self.original_title = unicode(self.title.text()).strip()

        self.show()

    def create_custom_column_editors(self):
        w = self.central_widget.widget(1)
        layout = w.layout()
        self.custom_column_widgets, self.__cc_spacers = \
            populate_metadata_page(layout, self.db, self.id, parent=w, bulk=False,
                two_column=tweaks['metadata_single_use_2_cols_for_custom_fields'])
        self.__custom_col_layouts = [layout]
        ans = self.custom_column_widgets
        for i in range(len(ans)-1):
            if len(ans[i+1].widgets) == 2:
                w.setTabOrder(ans[i].widgets[-1], ans[i+1].widgets[1])
            else:
                w.setTabOrder(ans[i].widgets[-1], ans[i+1].widgets[0])
            for c in range(2, len(ans[i].widgets), 2):
                w.setTabOrder(ans[i].widgets[c-1], ans[i].widgets[c+1])

    def title_box_changed(self, txt):
        ts = unicode(txt)
        ts = title_sort(ts)
        self.mark_box_as_ok(control = self.title_sort, tt=self.ts_tooltips,
                            normal=(unicode(self.title_sort.text()) == ts))

    def title_sort_box_changed(self, txt):
        ts = unicode(txt)
        self.mark_box_as_ok(control = self.title_sort, tt=self.ts_tooltips,
                            normal=(title_sort(unicode(self.title.text())) == ts))

    def authors_box_changed(self, txt):
        aus = unicode(txt)
        aus = re.sub(r'\s+et al\.$', '', aus)
        aus = self.db.author_sort_from_authors(string_to_authors(aus))
        self.mark_box_as_ok(control = self.author_sort, tt=self.aus_tooltips,
                            normal=(unicode(self.author_sort.text()) == aus))

    def author_sort_box_changed(self, txt):
        au = unicode(self.authors.text())
        au = re.sub(r'\s+et al\.$', '', au)
        au = self.db.author_sort_from_authors(string_to_authors(au))
        self.mark_box_as_ok(control = self.author_sort, tt=self.aus_tooltips,
                            normal=(au == txt))

    def mark_box_as_ok(self, control, tt, normal=True):
        if normal:
            col = 'rgb(0, 255, 0, 20%)'
        else:
            col = 'rgb(255, 0, 0, 20%)'
        control.setStyleSheet('QLineEdit { color: black; '
                              'background-color: %s; }'%col)
        tt = tt[0] if normal else tt[1]
        control.setToolTip(tt)

    def validate_isbn(self, isbn):
        isbn = unicode(isbn).strip()
        if not isbn:
            self.isbn.setStyleSheet('QLineEdit { background-color: rgba(0,255,0,0%) }')
            self.isbn.setToolTip(_('This ISBN number is valid'))
            return

        if check_isbn(isbn):
            self.isbn.setStyleSheet('QLineEdit { background-color: rgba(0,255,0,20%) }')
            self.isbn.setToolTip(_('This ISBN number is valid'))
        else:
            self.isbn.setStyleSheet('QLineEdit { background-color: rgba(255,0,0,20%) }')
            self.isbn.setToolTip(_('This ISBN number is invalid'))

    def deduce_author_sort(self):
        au = unicode(self.authors.text())
        au = re.sub(r'\s+et al\.$', '', au)
        authors = string_to_authors(au)
        self.author_sort.setText(self.db.author_sort_from_authors(authors))

    def deduce_title_sort(self):
        ts = unicode(self.title.text())
        self.title_sort.setText(title_sort(ts))

    def swap_title_author(self):
        title = self.title.text()
        self.title.setText(self.authors.text())
        self.authors.setText(title)
        self.deduce_author_sort()
        self.deduce_title_sort()

    def initialize_combos(self):
        self.initalize_authors()
        self.initialize_series()
        self.initialize_publisher()

        self.layout().activate()

    def initalize_authors(self):
        all_authors = self.db.all_authors()
        all_authors.sort(key=lambda x : sort_key(x[1]))
        for i in all_authors:
            id, name = i
            name = [name.strip().replace('|', ',') for n in name.split(',')]
            self.authors.addItem(authors_to_string(name))

        au = self.db.authors(self.row)
        if not au:
            au = _('Unknown')
        au = ' & '.join([a.strip().replace('|', ',') for a in au.split(',')])
        self.authors.setEditText(au)

    def initialize_series(self):
        self.series.setSizeAdjustPolicy(self.series.AdjustToContentsOnFirstShow)
        all_series = self.db.all_series()
        all_series.sort(key=lambda x : sort_key(x[1]))
        series_id = self.db.series_id(self.row)
        idx, c = None, 0
        for i in all_series:
            id, name = i
            if id == series_id:
                idx = c
            self.series.addItem(name)
            c += 1

        self.series.lineEdit().setText('')
        if idx is not None:
            self.series.setCurrentIndex(idx)
            self.enable_series_index()

    def initialize_publisher(self):
        all_publishers = self.db.all_publishers()
        all_publishers.sort(key=lambda x : sort_key(x[1]))
        publisher_id = self.db.publisher_id(self.row)
        idx, c = None, 0
        for i in all_publishers:
            id, name = i
            if id == publisher_id:
                idx = c
            self.publisher.addItem(name)
            c += 1

        self.publisher.setEditText('')
        if idx is not None:
            self.publisher.setCurrentIndex(idx)

    def edit_tags(self):
        if self.tags.text() != self.original_tags:
            if question_dialog(self, _('Tags changed'),
                    _('You have changed the tags. In order to use the tags'
                       ' editor, you must either discard or apply these '
                       'changes'), show_copy_button=False,
                    buttons=QMessageBox.Apply|QMessageBox.Discard,
                    yes_button=QMessageBox.Apply):
                self.apply_tags(commit=True, notify=True)
                self.original_tags = unicode(self.tags.text())
            else:
                self.tags.setText(self.original_tags)
        d = TagEditor(self, self.db, self.row)
        d.exec_()
        if d.result() == QDialog.Accepted:
            tag_string = ', '.join(d.tags)
            self.tags.setText(tag_string)
            self.tags.update_tags_cache(self.db.all_tags())


    def fetch_metadata(self):
        isbn   = re.sub(r'[^0-9a-zA-Z]', '', unicode(self.isbn.text()))
        title  = unicode(self.title.text())
        try:
            author = string_to_authors(unicode(self.authors.text()))[0]
        except:
            author = ''
        publisher = unicode(self.publisher.currentText())
        if isbn or title or author or publisher:
            d = FetchMetadata(self, isbn, title, author, publisher, self.timeout)
            self._fetch_metadata_scope = d
            with d:
                if d.exec_() == QDialog.Accepted:
                    book = d.selected_book()
                    if book:
                        if d.opt_get_social_metadata.isChecked():
                            d2 = SocialMetadata(book, self)
                            d2.exec_()
                            if d2.timed_out:
                                warning_dialog(self, _('Timed out'),
                                    _('The download of social'
                                    ' metadata timed out, the servers are'
                                    ' probably busy. Try again later.'),
                                    show=True)
                            elif d2.exceptions:
                                det = '\n'.join([x[0]+'\n\n'+x[-1]+'\n\n\n' for
                                    x in d2.exceptions])
                                warning_dialog(self, _('There were errors'),
                                       _('There were errors downloading social metadata'),
                                       det_msg=det, show=True)
                        else:
                            book.tags = []
                        if d.opt_overwrite_author_title_metadata.isChecked():
                            self.title.setText(book.title)
                            self.authors.setText(authors_to_string(book.authors))
                            if book.author_sort: self.author_sort.setText(book.author_sort)
                        if book.publisher: self.publisher.setEditText(book.publisher)
                        if book.isbn: self.isbn.setText(book.isbn)
                        if book.pubdate:
                            dt = book.pubdate
                            self.pubdate.setDate(QDate(dt.year, dt.month, dt.day))
                        summ = book.comments
                        if summ:
                            prefix = self.comments.html
                            if prefix:
                                prefix += '\n'
                            self.comments.html = prefix + comments_to_html(summ)
                        if book.rating is not None:
                            self.rating.setValue(int(book.rating))
                        if book.tags:
                            self.tags.setText(', '.join(book.tags))
                        if book.series is not None:
                            if self.series.text() is None or self.series.text() == '':
                                self.series.setText(book.series)
                                if book.series_index is not None:
                                    self.series_index.setValue(book.series_index)
                        if book.has_cover:
                            if d.opt_auto_download_cover.isChecked():
                                self.fetch_cover()
                            else:
                                self.fetch_cover_button.setFocus(Qt.OtherFocusReason)
        else:
            error_dialog(self, _('Cannot fetch metadata'),
                         _('You must specify at least one of ISBN, Title, '
                           'Authors or Publisher'), show=True)
            self.title.setFocus(Qt.OtherFocusReason)

    def enable_series_index(self, *args):
        self.series_index.setEnabled(True)

    def increment_series_index(self):
        if self.db is not None:
            try:
                series = unicode(self.series.text()).strip()
                if series and series != self.original_series_name:
                    ns = 1
                    if tweaks['series_index_auto_increment'] != 'const':
                        ns = self.db.get_next_series_num_for(series)
                    self.series_index.setValue(ns)
                    self.original_series_name = series
            except:
                traceback.print_exc()

    def remove_unused_series(self):
        self.db.remove_unused_series()
        idx = unicode(self.series.currentText())
        self.series.clear()
        self.initialize_series()
        if idx:
            for i in range(self.series.count()):
                if unicode(self.series.itemText(i)) == idx:
                    self.series.setCurrentIndex(i)
                    break

    def apply_tags(self, commit=False, notify=False):
        self.db.set_tags(self.id, [x.strip() for x in
            unicode(self.tags.text()).split(',')],
                notify=notify, commit=commit)

    def next_triggered(self, row_delta, *args):
        self.row_delta = row_delta
        self.accept()

    def accept(self):
        try:
            if self.formats_changed:
                self.sync_formats()
            title = unicode(self.title.text()).strip()
            if title != self.original_title:
                self.db.set_title(self.id, title, notify=False)
            # This must be after setting the title because of the DB update trigger
            ts = unicode(self.title_sort.text()).strip()
            if ts:
                self.db.set_title_sort(self.id, ts, notify=False, commit=False)
            au = unicode(self.authors.text()).strip()
            if au and au != self.original_author:
                self.db.set_authors(self.id, string_to_authors(au), notify=False)
            aus = unicode(self.author_sort.text()).strip()
            if aus:
                self.db.set_author_sort(self.id, aus, notify=False, commit=False)
            self.db.set_isbn(self.id,
                             re.sub(r'[^0-9a-zA-Z]', '',
                                 unicode(self.isbn.text()).strip()),
                             notify=False, commit=False)
            self.db.set_rating(self.id, 2*self.rating.value(), notify=False,
                               commit=False)
            self.apply_tags()
            self.db.set_publisher(self.id,
                    unicode(self.publisher.currentText()).strip(),
                                  notify=False, commit=False)
            self.db.set_series(self.id,
                    unicode(self.series.currentText()).strip(), notify=False,
                    commit=False)
            self.db.set_series_index(self.id, self.series_index.value(),
                                     notify=False, commit=False)
            self.db.set_comment(self.id,
                    self.comments.html,
                                notify=False, commit=False)
            d = self.pubdate.date()
            d = qt_to_dt(d)
            self.db.set_pubdate(self.id, d, notify=False, commit=False)
            d = self.date.date()
            d = qt_to_dt(d)
            if d != self.orig_date:
                self.db.set_timestamp(self.id, d, notify=False, commit=False)
            self.db.commit()

            if self.cover_changed:
                if self.cover_data is not None:
                    self.db.set_cover(self.id, self.cover_data)
                else:
                    self.db.remove_cover(self.id)
            for w in getattr(self, 'custom_column_widgets', []):
                w.commit(self.id)
            self.db.commit()
        except IOError, err:
            if err.errno == 13: # Permission denied
                fname = err.filename if err.filename else 'file'
                return error_dialog(self, _('Permission denied'),
                        _('Could not open %s. Is it being used by another'
                        ' program?')%fname, det_msg=traceback.format_exc(),
                        show=True)
            raise
        self.save_state()
        self.cover_fetcher = None
        QDialog.accept(self)

    def reject(self, *args):
        self.save_state()
        self.cover_fetcher = None
        QDialog.reject(self, *args)

    def read_state(self):
        wg = dynamic.get('metasingle_window_geometry2', None)
        ss = dynamic.get('metasingle_splitter_state2', None)
        if wg is not None:
            self.restoreGeometry(wg)
        if ss is not None:
            self.splitter.restoreState(ss)

    def save_state(self):
        dynamic.set('metasingle_window_geometry2', bytes(self.saveGeometry()))
        dynamic.set('metasingle_splitter_state2',
                bytes(self.splitter.saveState()))

    def break_cycles(self):
        # Break any reference cycles that could prevent python
        # from garbage collecting this dialog
        def disconnect(signal):
            try:
                signal.disconnect()
            except:
                pass # Fails if view format was never connected
        disconnect(self.view_format)
        for b in ('next_button', 'prev_button'):
            x = getattr(self, b, None)
            if x is not None:
                disconnect(x.clicked)

if __name__ == '__main__':
    from calibre.library import db
    from PyQt4.Qt import QApplication
    from calibre.utils.mem import memory
    import gc


    app = QApplication([])
    db = db()

    # Initialize all Qt Objects once
    d = MetadataSingleDialog(None, 4, db)
    d.break_cycles()
    d.reject()
    del d

    for i in range(5):
        gc.collect()
    before = memory()

    d = MetadataSingleDialog(None, 4, db)
    d.reject()
    d.break_cycles()
    del d

    for i in range(5):
        gc.collect()
    print 'Used memory:', memory(before)/1024.**2, 'MB'


