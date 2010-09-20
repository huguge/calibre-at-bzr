__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to edit metadata in bulk'''

from threading import Thread
import re, string

from PyQt4.Qt import Qt, QDialog, QGridLayout
from PyQt4 import QtGui

from calibre.gui2.dialogs.metadata_bulk_ui import Ui_MetadataBulkDialog
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.ebooks.metadata import string_to_authors, authors_to_string
from calibre.gui2.custom_column_widgets import populate_metadata_page
from calibre.gui2.dialogs.progress import BlockingBusy
from calibre.gui2 import error_dialog, Dispatcher
from calibre.utils.config import dynamic

class Worker(Thread):

    def __init__(self, args, db, ids, cc_widgets, callback):
        Thread.__init__(self)
        self.args = args
        self.db = db
        self.ids = ids
        self.error = None
        self.callback = callback
        self.cc_widgets = cc_widgets

    def doit(self):
        remove, add, au, aus, do_aus, rating, pub, do_series, \
            do_autonumber, do_remove_format, remove_format, do_swap_ta, \
            do_remove_conv, do_auto_author, series = self.args

        # first loop: do author and title. These will commit at the end of each
        # operation, because each operation modifies the file system. We want to
        # try hard to keep the DB and the file system in sync, even in the face
        # of exceptions or forced exits.
        for id in self.ids:
            if do_swap_ta:
                title = self.db.title(id, index_is_id=True)
                aum = self.db.authors(id, index_is_id=True)
                if aum:
                    aum = [a.strip().replace('|', ',') for a in aum.split(',')]
                    new_title = authors_to_string(aum)
                    self.db.set_title(id, new_title, notify=False)
                if title:
                    new_authors = string_to_authors(title)
                    self.db.set_authors(id, new_authors, notify=False)

            if au:
                self.db.set_authors(id, string_to_authors(au), notify=False)

        # All of these just affect the DB, so we can tolerate a total rollback
        for id in self.ids:
            if do_auto_author:
                x = self.db.author_sort_from_book(id, index_is_id=True)
                if x:
                    self.db.set_author_sort(id, x, notify=False, commit=False)

            if aus and do_aus:
                self.db.set_author_sort(id, aus, notify=False, commit=False)

            if rating != -1:
                self.db.set_rating(id, 2*rating, notify=False, commit=False)

            if pub:
                self.db.set_publisher(id, pub, notify=False, commit=False)

            if do_series:
                next = self.db.get_next_series_num_for(series)
                self.db.set_series(id, series, notify=False, commit=False)
                num = next if do_autonumber and series else 1.0
                self.db.set_series_index(id, num, notify=False, commit=False)

            if do_remove_format:
                self.db.remove_format(id, remove_format, index_is_id=True, notify=False, commit=False)

            if do_remove_conv:
                self.db.delete_conversion_options(id, 'PIPE', commit=False)
        self.db.commit()

        for w in self.cc_widgets:
            w.commit(self.ids)
        self.db.bulk_modify_tags(self.ids, add=add, remove=remove,
                notify=False)

    def run(self):
        try:
            self.doit()
        except Exception, err:
            import traceback
            try:
                err = unicode(err)
            except:
                err = repr(err)
            self.error = (err, traceback.format_exc())

        self.callback()

class SafeFormat(string.Formatter):
    '''
    Provides a format function that substitutes '' for any missing value
    '''
    def get_value(self, key, args, vals):
        v = vals.get(key, None)
        if v is None:
            return ''
        if isinstance(v, (tuple, list)):
            v = ','.join(v)
        return v

composite_formatter = SafeFormat()

def format_composite(x, mi):
    try:
        ans = composite_formatter.vformat(x, [], mi).strip()
    except:
        ans = x
    return ans

class MetadataBulkDialog(QDialog, Ui_MetadataBulkDialog):

    s_r_functions = {       ''              : lambda x: x,
                            _('Lower Case') : lambda x: x.lower(),
                            _('Upper Case') : lambda x: x.upper(),
                            _('Title Case') : lambda x: x.title(),
                    }

    s_r_match_modes = [     _('Character match'),
                            _('Regular Expression'),
                      ]

    s_r_replace_modes = [   _('Replace field'),
                            _('Prepend to field'),
                            _('Append to field'),
                        ]

    def __init__(self, window, rows, db):
        QDialog.__init__(self, window)
        Ui_MetadataBulkDialog.__init__(self)
        self.setupUi(self)
        self.db = db
        self.ids = [db.id(r) for r in rows]
        self.box_title.setText('<p>' +
                _('Editing meta information for <b>%d books</b>') %
                len(rows))
        self.write_series = False
        self.changed = False

        all_tags = self.db.all_tags()
        self.tags.update_tags_cache(all_tags)
        self.remove_tags.update_tags_cache(all_tags)

        self.initialize_combos()

        for f in self.db.all_formats():
            self.remove_format.addItem(f)

        self.remove_format.setCurrentIndex(-1)

        self.series.currentIndexChanged[int].connect(self.series_changed)
        self.series.editTextChanged.connect(self.series_changed)
        self.tag_editor_button.clicked.connect(self.tag_editor)

        if len(db.custom_column_label_map) == 0:
            self.central_widget.removeTab(1)
        else:
            self.create_custom_column_editors()

        self.prepare_search_and_replace()
        self.exec_()

    def prepare_search_and_replace(self):
        self.search_for.initialize('bulk_edit_search_for')
        self.replace_with.initialize('bulk_edit_replace_with')
        self.test_text.initialize('bulk_edit_test_test')
        fields = ['']
        fm = self.db.field_metadata
        for f in fm:
            if (f in ['author_sort'] or (
                fm[f]['datatype'] == 'text' or fm[f]['datatype'] == 'series')
                    and fm[f].get('search_terms', None)
                    and f not in ['formats', 'ondevice']):
                fields.append(f)
        fields.sort()
        self.search_field.addItems(fields)
        self.search_field.setMaxVisibleItems(min(len(fields), 20))
        self.destination_field.addItems(fields)
        self.destination_field.setMaxVisibleItems(min(len(fields), 20))
        offset = 10
        self.s_r_number_of_books = min(7, len(self.ids))
        for i in range(1,self.s_r_number_of_books+1):
            w = QtGui.QLabel(self.tabWidgetPage3)
            w.setText(_('Book %d:')%i)
            self.testgrid.addWidget(w, i+offset, 0, 1, 1)
            w = QtGui.QLineEdit(self.tabWidgetPage3)
            w.setReadOnly(True)
            name = 'book_%d_text'%i
            setattr(self, name, w)
            self.book_1_text.setObjectName(name)
            self.testgrid.addWidget(w, i+offset, 1, 1, 1)
            w = QtGui.QLineEdit(self.tabWidgetPage3)
            w.setReadOnly(True)
            name = 'book_%d_result'%i
            setattr(self, name, w)
            self.book_1_text.setObjectName(name)
            self.testgrid.addWidget(w, i+offset, 2, 1, 1)

        self.s_r_heading.setText('<p>'+ _(
                 '<b>You can destroy your library using this feature.</b> '
                 'Changes are permanent. There is no undo function. '
                 ' This feature is experimental, and there may be bugs. '
                 'You are strongly encouraged to back up your library '
                 'before proceeding.'
                 ) + '<p>' + _(
                 'Search and replace in text fields using character matching '
                 'or regular expressions. In character mode, search text '
                 'found in the specified field is replaced with replace '
                 'text. In regular expression mode, the search text is an '
                 'arbitrary python-compatible regular expression. The '
                 'replacement text can contain backreferences to parenthesized '
                 'expressions in the pattern. The search is not anchored, '
                 'and can match and replace multiple times on the same string. '
                 'See <a href="http://docs.python.org/library/re.html"> '
                 'this reference</a> for more information, and in particular '
                 'the \'sub\' function.'
                 ))
        self.search_mode.addItems(self.s_r_match_modes)
        self.search_mode.setCurrentIndex(dynamic.get('s_r_search_mode', 0))
        self.replace_mode.addItems(self.s_r_replace_modes)
        self.replace_mode.setCurrentIndex(0)

        self.s_r_search_mode = 0
        self.s_r_error = None
        self.s_r_obj = None

        self.replace_func.addItems(sorted(self.s_r_functions.keys()))
        self.search_mode.currentIndexChanged[int].connect(self.s_r_search_mode_changed)
        self.search_field.currentIndexChanged[str].connect(self.s_r_search_field_changed)
        self.destination_field.currentIndexChanged[str].connect(self.s_r_destination_field_changed)

        self.replace_mode.currentIndexChanged[int].connect(self.s_r_paint_results)
        self.replace_func.currentIndexChanged[str].connect(self.s_r_paint_results)
        self.search_for.editTextChanged[str].connect(self.s_r_paint_results)
        self.replace_with.editTextChanged[str].connect(self.s_r_paint_results)
        self.test_text.editTextChanged[str].connect(self.s_r_paint_results)
        self.comma_separated.stateChanged.connect(self.s_r_paint_results)
        self.case_sensitive.stateChanged.connect(self.s_r_paint_results)
        self.central_widget.setCurrentIndex(0)

        self.search_for.completer().setCaseSensitivity(Qt.CaseSensitive)
        self.replace_with.completer().setCaseSensitivity(Qt.CaseSensitive)

        self.s_r_search_mode_changed(self.search_mode.currentIndex())

    def s_r_get_field(self, mi, field):
        if field:
            fm = self.db.metadata_for_field(field)
            val = mi.get(field, None)
            if val is None:
                val = []
            elif not fm['is_multiple']:
                val = [val]
            elif field == 'authors':
                val = [v.replace(',', '|') for v in val]
        else:
            val = []
        return val

    def s_r_search_field_changed(self, txt):
        txt = unicode(txt)
        for i in range(0, self.s_r_number_of_books):
            w = getattr(self, 'book_%d_text'%(i+1))
            mi = self.db.get_metadata(self.ids[i], index_is_id=True)
            src = unicode(self.search_field.currentText())
            t = self.s_r_get_field(mi, src)
            w.setText(''.join(t[0:1]))
        self.s_r_paint_results(None)

    def s_r_destination_field_changed(self, txt):
        txt = unicode(txt)
        self.comma_separated.setEnabled(True)
        if txt:
            fm = self.db.metadata_for_field(txt)
            if fm['is_multiple']:
                self.comma_separated.setEnabled(False)
                self.comma_separated.setChecked(True)
        self.s_r_paint_results(None)

    def s_r_search_mode_changed(self, val):
        if val == 0:
            self.destination_field.setCurrentIndex(0)
            self.destination_field.setVisible(False)
            self.destination_field_label.setVisible(False)
            self.replace_mode.setCurrentIndex(0)
            self.replace_mode.setVisible(False)
            self.replace_mode_label.setVisible(False)
            self.comma_separated.setVisible(False)
        else:
            self.destination_field.setVisible(True)
            self.destination_field_label.setVisible(True)
            self.replace_mode.setVisible(True)
            self.replace_mode_label.setVisible(True)
            self.comma_separated.setVisible(True)
        self.s_r_paint_results(None)

    def s_r_set_colors(self):
        if self.s_r_error is not None:
            col = 'rgb(255, 0, 0, 20%)'
            self.test_result.setText(self.s_r_error.message)
        else:
            col = 'rgb(0, 255, 0, 20%)'
        self.test_result.setStyleSheet('QLineEdit { color: black; '
                                       'background-color: %s; }'%col)
        for i in range(0,self.s_r_number_of_books):
            getattr(self, 'book_%d_result'%(i+1)).setText('')

    def s_r_func(self, match):
        rfunc = self.s_r_functions[unicode(self.replace_func.currentText())]
        rtext = unicode(self.replace_with.text())
        rtext = match.expand(rtext)
        return rfunc(rtext)

    def s_r_do_regexp(self, mi):
        src_field = unicode(self.search_field.currentText())
        src = self.s_r_get_field(mi, src_field)
        result = []
        rfunc = self.s_r_functions[unicode(self.replace_func.currentText())]
        for s in src:
            t = self.s_r_obj.sub(self.s_r_func, s)
            if self.search_mode.currentIndex() == 0:
                t = rfunc(t)
            result.append(t)
        return result

    def s_r_do_destination(self, mi, val):
        src = unicode(self.search_field.currentText())
        if src == '':
            return ''
        dest = unicode(self.destination_field.currentText())
        if dest == '':
            dest = src
        dest_mode = self.replace_mode.currentIndex()

        if dest_mode != 0:
            dest_val = mi.get(dest, '')
            if dest_val is None:
                dest_val = []
            elif isinstance(dest_val, list):
                if dest == 'authors':
                    dest_val = [v.replace(',', '|') for v in dest_val]
            else:
                dest_val = [dest_val]
        else:
            dest_val = []

        if len(val) > 0:
            if src == 'authors':
                val = [v.replace(',', '|') for v in val]
        if dest_mode == 1:
            val.extend(dest_val)
        elif dest_mode == 2:
            val[0:0] = dest_val
        return val

    def s_r_replace_mode_separator(self):
        if self.comma_separated.isChecked():
            return ','
        return ''

    def s_r_paint_results(self, txt):
        self.s_r_error = None
        self.s_r_set_colors()

        if self.case_sensitive.isChecked():
            flags = 0
        else:
            flags = re.I

        try:
            if self.search_mode.currentIndex() == 0:
                self.s_r_obj = re.compile(re.escape(unicode(self.search_for.text())), flags)
            else:
                self.s_r_obj = re.compile(unicode(self.search_for.text()), flags)
        except Exception as e:
            self.s_r_obj = None
            self.s_r_error = e
            self.s_r_set_colors()
            return

        try:
            self.test_result.setText(self.s_r_obj.sub(self.s_r_func,
                                     unicode(self.test_text.text())))
        except Exception as e:
            self.s_r_error = e
            self.s_r_set_colors()
            return

        for i in range(0,self.s_r_number_of_books):
            mi = self.db.get_metadata(self.ids[i], index_is_id=True)
            wr = getattr(self, 'book_%d_result'%(i+1))
            try:
                result = self.s_r_do_regexp(mi)
                t = self.s_r_do_destination(mi, result[0:1])
                t = self.s_r_replace_mode_separator().join(t)
                wr.setText(t)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.s_r_error = e
                self.s_r_set_colors()
                break

    def do_search_replace(self):
        source = unicode(self.search_field.currentText())
        if not source or not self.s_r_obj:
            return
        dest = unicode(self.destination_field.currentText())
        if not dest:
            dest = source
        dfm = self.db.field_metadata[dest]

        for id in self.ids:
            mi = self.db.get_metadata(id, index_is_id=True,)
            val = mi.get(source)
            if val is None:
                continue
            val = self.s_r_do_regexp(mi)
            val = self.s_r_do_destination(mi, val)
            if dfm['is_multiple']:
                if dfm['is_custom']:
                    # The standard tags and authors values want to be lists.
                    # All custom columns are to be strings
                    val = dfm['is_multiple'].join(val)
            else:
                val = self.s_r_replace_mode_separator().join(val)

            if dfm['is_custom']:
                extra = self.db.get_custom_extra(id, label=dfm['label'], index_is_id=True)
                self.db.set_custom(id, val, label=dfm['label'], extra=extra,
                                   commit=False)
            else:
                if dest == 'comments':
                    setter = self.db.set_comment
                else:
                    setter = getattr(self.db, 'set_'+dest)
                setter(id, val, notify=False, commit=False)
        self.db.commit()
        dynamic['s_r_search_mode'] = self.search_mode.currentIndex()

    def create_custom_column_editors(self):
        w = self.central_widget.widget(1)
        layout = QGridLayout()
        self.custom_column_widgets, self.__cc_spacers = \
            populate_metadata_page(layout, self.db, self.ids, parent=w,
                                   two_column=False, bulk=True)
        w.setLayout(layout)
        self.__custom_col_layouts = [layout]
        ans = self.custom_column_widgets
        for i in range(len(ans)-1):
            w.setTabOrder(ans[i].widgets[-1], ans[i+1].widgets[1])
            for c in range(2, len(ans[i].widgets), 2):
                w.setTabOrder(ans[i].widgets[c-1], ans[i].widgets[c+1])

    def initialize_combos(self):
        self.initalize_authors()
        self.initialize_series()
        self.initialize_publisher()

    def initalize_authors(self):
        all_authors = self.db.all_authors()
        all_authors.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_authors:
            id, name = i
            name = authors_to_string([name.strip().replace('|', ',') for n in name.split(',')])
            self.authors.addItem(name)
        self.authors.setEditText('')

    def initialize_series(self):
        all_series = self.db.all_series()
        all_series.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_series:
            id, name = i
            self.series.addItem(name)
        self.series.setEditText('')

    def initialize_publisher(self):
        all_publishers = self.db.all_publishers()
        all_publishers.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_publishers:
            id, name = i
            self.publisher.addItem(name)
        self.publisher.setEditText('')

    def tag_editor(self, *args):
        d = TagEditor(self, self.db, None)
        d.exec_()
        if d.result() == QDialog.Accepted:
            tag_string = ', '.join(d.tags)
            self.tags.setText(tag_string)
            self.tags.update_tags_cache(self.db.all_tags())
            self.remove_tags.update_tags_cache(self.db.all_tags())

    def accept(self):
        if len(self.ids) < 1:
            return QDialog.accept(self)

        if self.s_r_error is not None:
            error_dialog(self, _('Search/replace invalid'),
                    _('Search pattern is invalid: %s')%self.s_r_error.message,
                    show=True)
            return False
        self.changed = bool(self.ids)
        # Cache values from GUI so that Qt widgets are not used in
        # non GUI thread
        for w in getattr(self, 'custom_column_widgets', []):
            w.gui_val

        if self.remove_all_tags.isChecked():
            remove = self.db.all_tags()
        else:
            remove = unicode(self.remove_tags.text()).strip().split(',')
        add = unicode(self.tags.text()).strip().split(',')
        au = unicode(self.authors.text())
        aus = unicode(self.author_sort.text())
        do_aus = self.author_sort.isEnabled()
        rating = self.rating.value()
        pub = unicode(self.publisher.text())
        do_series = self.write_series
        series = unicode(self.series.currentText()).strip()
        do_autonumber = self.autonumber_series.isChecked()
        do_remove_format = self.remove_format.currentIndex() > -1
        remove_format = unicode(self.remove_format.currentText())
        do_swap_ta = self.swap_title_and_author.isChecked()
        do_remove_conv = self.remove_conversion_settings.isChecked()
        do_auto_author = self.auto_author_sort.isChecked()

        args = (remove, add, au, aus, do_aus, rating, pub, do_series,
                do_autonumber, do_remove_format, remove_format, do_swap_ta,
                do_remove_conv, do_auto_author, series)

        bb = BlockingBusy(_('Applying changes to %d books. This may take a while.')
                %len(self.ids), parent=self)
        self.worker = Worker(args, self.db, self.ids,
                getattr(self, 'custom_column_widgets', []),
                Dispatcher(bb.accept, parent=bb))
        self.worker.start()
        bb.exec_()

        if self.worker.error is not None:
            return error_dialog(self, _('Failed'),
                    self.worker.error[0], det_msg=self.worker.error[1],
                    show=True)

        self.do_search_replace()

        self.db.clean()
        return QDialog.accept(self)


    def series_changed(self, *args):
        self.write_series = True

