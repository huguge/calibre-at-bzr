#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial

from PyQt4.Qt import Qt, QMenu, QModelIndex, QTimer

from calibre.gui2 import error_dialog, config, Dispatcher
from calibre.gui2.dialogs.metadata_single import MetadataSingleDialog
from calibre.gui2.dialogs.metadata_bulk import MetadataBulkDialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.tag_list_editor import TagListEditor
from calibre.gui2.actions import InterfaceAction
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.icu import sort_key
from calibre.utils.config import test_eight_code

class EditMetadataAction(InterfaceAction):

    name = 'Edit Metadata'
    action_spec = (_('Edit metadata'), 'edit_input.png', None, _('E'))
    action_type = 'current'

    def genesis(self):
        self.create_action(spec=(_('Merge book records'), 'merge_books.png',
            None, _('M')), attr='action_merge')
        md = QMenu()
        md.addAction(_('Edit metadata individually'),
                partial(self.edit_metadata, False, bulk=False))
        md.addSeparator()
        md.addAction(_('Edit metadata in bulk'),
                partial(self.edit_metadata, False, bulk=True))
        md.addSeparator()
        if test_eight_code:
            dall = self.download_metadata
        else:
            dall = partial(self.download_metadata_old, False, covers=True)
            dident = partial(self.download_metadata_old, False, covers=False)
            dcovers = partial(self.download_metadata_old, False, covers=True,
                    set_metadata=False, set_social_metadata=False)

        md.addAction(_('Download metadata and covers'), dall,
                Qt.ControlModifier+Qt.Key_D)
        if not test_eight_code:
            md.addAction(_('Download only metadata'), dident)
            md.addAction(_('Download only covers'), dcovers)
            md.addAction(_('Download only social metadata'),
                partial(self.download_metadata_old, False, covers=False,
                    set_metadata=False, set_social_metadata=True))
        self.metadata_menu = md

        mb = QMenu()
        mb.addAction(_('Merge into first selected book - delete others'),
                self.merge_books)
        mb.addSeparator()
        mb.addAction(_('Merge into first selected book - keep others'),
                partial(self.merge_books, safe_merge=True),
                Qt.AltModifier+Qt.Key_M)
        mb.addSeparator()
        mb.addAction(_('Merge only formats into first selected book - delete others'),
                partial(self.merge_books, merge_only_formats=True),
                Qt.AltModifier+Qt.ShiftModifier+Qt.Key_M)
        self.merge_menu = mb
        self.action_merge.setMenu(mb)
        md.addSeparator()
        md.addAction(self.action_merge)

        self.qaction.triggered.connect(self.edit_metadata)
        self.qaction.setMenu(md)
        self.action_merge.triggered.connect(self.merge_books)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)
        self.action_merge.setEnabled(enabled)

    def download_metadata(self, ids=None):
        if ids is None:
            rows = self.gui.library_view.selectionModel().selectedRows()
            if not rows or len(rows) == 0:
                return error_dialog(self.gui, _('Cannot download metadata'),
                            _('No books selected'), show=True)
            db = self.gui.library_view.model().db
            ids = [db.id(row.row()) for row in rows]
        from calibre.gui2.metadata.bulk_download2 import start_download
        start_download(self.gui, ids,
                Dispatcher(self.bulk_metadata_downloaded))

    def bulk_metadata_downloaded(self, job):
        if job.failed:
            self.gui.job_exception(job, dialog_title=_('Failed to download metadata'))
            return
        from calibre.gui2.metadata.bulk_download2 import proceed
        proceed(self.gui, job)

    def download_metadata_old(self, checked, covers=True, set_metadata=True,
            set_social_metadata=None):
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot download metadata'),
                             _('No books selected'))
            d.exec_()
            return
        db = self.gui.library_view.model().db
        ids = [db.id(row.row()) for row in rows]
        self.do_download_metadata(ids, covers=covers,
                set_metadata=set_metadata,
                set_social_metadata=set_social_metadata)

    def do_download_metadata(self, ids, covers=True, set_metadata=True,
            set_social_metadata=None):
        m = self.gui.library_view.model()
        db = m.db
        if set_social_metadata is None:
            get_social_metadata = config['get_social_metadata']
        else:
            get_social_metadata = set_social_metadata
        from calibre.gui2.metadata.bulk_download import DoDownload
        if set_social_metadata is not None and set_social_metadata:
            x = _('social metadata')
        else:
            x = _('covers') if covers and not set_metadata else _('metadata')
        title = _('Downloading {0} for {1} book(s)').format(x, len(ids))
        self._download_book_metadata = DoDownload(self.gui, title, db, ids,
                get_covers=covers, set_metadata=set_metadata,
                get_social_metadata=get_social_metadata)
        m.stop_metadata_backup()
        try:
            self._download_book_metadata.exec_()
        finally:
            m.start_metadata_backup()
        cr = self.gui.library_view.currentIndex().row()
        x = self._download_book_metadata
        if x.updated:
            self.gui.library_view.model().refresh_ids(
                x.updated, cr)
            if self.gui.cover_flow:
                self.gui.cover_flow.dataChanged()

    def edit_metadata(self, checked, bulk=None):
        '''
        Edit metadata of selected books in library.
        '''
        rows = self.gui.library_view.selectionModel().selectedRows()
        previous = self.gui.library_view.currentIndex()
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot edit metadata'),
                             _('No books selected'))
            d.exec_()
            return

        if bulk or (bulk is None and len(rows) > 1):
            return self.edit_bulk_metadata(checked)

        row_list = [r.row() for r in rows]
        current_row = 0

        if len(row_list) == 1:
            cr = row_list[0]
            row_list = \
                list(range(self.gui.library_view.model().rowCount(QModelIndex())))
            current_row = row_list.index(cr)

        func = (self.do_edit_metadata if test_eight_code else
                    self.do_edit_metadata_old)
        changed, rows_to_refresh = func(row_list, current_row)

        m = self.gui.library_view.model()

        if rows_to_refresh:
            m.refresh_rows(rows_to_refresh)

        if changed:
            m.refresh_ids(list(changed))
            current = self.gui.library_view.currentIndex()
            if self.gui.cover_flow:
                self.gui.cover_flow.dataChanged()
            m.current_changed(current, previous)
            self.gui.tags_view.recount()

    def do_edit_metadata_old(self, row_list, current_row):
        changed = set([])
        db = self.gui.library_view.model().db

        while True:
            prev = next_ = None
            if current_row > 0:
                prev = db.title(row_list[current_row-1])
            if current_row < len(row_list) - 1:
                next_ = db.title(row_list[current_row+1])

            d = MetadataSingleDialog(self.gui, row_list[current_row], db,
                    prev=prev, next_=next_)
            d.view_format.connect(lambda
                    fmt:self.gui.iactions['View'].view_format(row_list[current_row],
                        fmt))
            ret = d.exec_()
            d.break_cycles()
            if ret != d.Accepted:
                break

            changed.add(d.id)
            self.gui.library_view.model().refresh_ids(list(d.books_to_refresh))
            if d.row_delta == 0:
                break
            current_row += d.row_delta
            self.gui.library_view.set_current_row(current_row)
            self.gui.library_view.scroll_to_row(current_row)
        return changed, set()

    def do_edit_metadata(self, row_list, current_row):
        from calibre.gui2.metadata.single import edit_metadata
        db = self.gui.library_view.model().db
        changed, rows_to_refresh = edit_metadata(db, row_list, current_row,
                parent=self.gui, view_slot=self.view_format_callback,
                set_current_callback=self.set_current_callback)
        return changed, rows_to_refresh

    def set_current_callback(self, id_):
        db = self.gui.library_view.model().db
        current_row = db.row(id_)
        self.gui.library_view.set_current_row(current_row)
        self.gui.library_view.scroll_to_row(current_row)

    def view_format_callback(self, id_, fmt):
        view = self.gui.iactions['View']
        if id_ is None:
            view._view_file(fmt)
        else:
            db = self.gui.library_view.model().db
            view.view_format(db.row(id_), fmt)


    def edit_bulk_metadata(self, checked):
        '''
        Edit metadata of selected books in library in bulk.
        '''
        rows = [r.row() for r in \
                self.gui.library_view.selectionModel().selectedRows()]
        m = self.gui.library_view.model()
        ids = [m.id(r) for r in rows]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot edit metadata'),
                    _('No books selected'))
            d.exec_()
            return
        # Prevent the TagView from updating due to signals from the database
        self.gui.tags_view.blockSignals(True)
        changed = False
        try:
            current_tab = 0
            while True:
                dialog = MetadataBulkDialog(self.gui, rows,
                                self.gui.library_view.model(), current_tab)
                if dialog.changed:
                    changed = True
                if not dialog.do_again:
                    break
                current_tab = dialog.central_widget.currentIndex()
        finally:
            self.gui.tags_view.blockSignals(False)
        if changed:
            m = self.gui.library_view.model()
            m.refresh(reset=False)
            m.research()
            self.gui.tags_view.recount()
            if self.gui.cover_flow:
                self.gui.cover_flow.dataChanged()
            self.gui.library_view.select_rows(ids)

    # Merge books {{{
    def merge_books(self, safe_merge=False, merge_only_formats=False):
        '''
        Merge selected books in library.
        '''
        if self.gui.stack.currentIndex() != 0:
            return
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, _('Cannot merge books'),
                                _('No books selected'), show=True)
        if len(rows) < 2:
            return error_dialog(self.gui, _('Cannot merge books'),
                        _('At least two books must be selected for merging'),
                        show=True)
        if len(rows) > 5:
            if not confirm('<p>'+_('You are about to merge more than 5 books.  '
                                    'Are you <b>sure</b> you want to proceed?')
                                +'</p>', 'merge_too_many_books', self.gui):
                return

        dest_id, src_books, src_ids = self.books_to_merge(rows)
        title = self.gui.library_view.model().db.title(dest_id, index_is_id=True)
        if safe_merge:
            if not confirm('<p>'+_(
                'Book formats and metadata from the selected books '
                'will be added to the <b>first selected book</b> (%s). '
                'ISBN will <i>not</i> be merged.<br><br> '
                'The second and subsequently selected books will not '
                'be deleted or changed.<br><br>'
                'Please confirm you want to proceed.')%title
            +'</p>', 'merge_books_safe', self.gui):
                return
            self.add_formats(dest_id, src_books)
            self.merge_metadata(dest_id, src_ids)
        elif merge_only_formats:
            if not confirm('<p>'+_(
                'Book formats from the selected books will be merged '
                'into the <b>first selected book</b> (%s). '
                'Metadata in the first selected book will not be changed.'
                'Author, Title, ISBN and all other metadata will <i>not</i> be merged.<br><br>'
                'After merger the second and subsequently '
                'selected books, with any metadata they have will be <b>deleted</b>. <br><br>'
                'All book formats of the first selected book will be kept '
                'and any duplicate formats in the second and subsequently selected books '
                'will be permanently <b>deleted</b> from your calibre library.<br><br>  '
                'Are you <b>sure</b> you want to proceed?')%title
            +'</p>', 'merge_only_formats', self.gui):
                return
            self.add_formats(dest_id, src_books)
            self.delete_books_after_merge(src_ids)
        else:
            if not confirm('<p>'+_(
                'Book formats and metadata from the selected books will be merged '
                'into the <b>first selected book</b> (%s). '
                'ISBN will <i>not</i> be merged.<br><br>'
                'After merger the second and '
                'subsequently selected books will be <b>deleted</b>. <br><br>'
                'All book formats of the first selected book will be kept '
                'and any duplicate formats in the second and subsequently selected books '
                'will be permanently <b>deleted</b> from your calibre library.<br><br>  '
                'Are you <b>sure</b> you want to proceed?')%title
            +'</p>', 'merge_books', self.gui):
                return
            self.add_formats(dest_id, src_books)
            self.merge_metadata(dest_id, src_ids)
            self.delete_books_after_merge(src_ids)
            # leave the selection highlight on first selected book
            dest_row = rows[0].row()
            for row in rows:
                if row.row() < rows[0].row():
                    dest_row -= 1
            ci = self.gui.library_view.model().index(dest_row, 0)
            if ci.isValid():
                self.gui.library_view.setCurrentIndex(ci)
                self.gui.library_view.model().current_changed(ci, ci)

    def add_formats(self, dest_id, src_books, replace=False):
        for src_book in src_books:
            if src_book:
                fmt = os.path.splitext(src_book)[-1].replace('.', '').upper()
                with open(src_book, 'rb') as f:
                    self.gui.library_view.model().db.add_format(dest_id, fmt, f, index_is_id=True,
                            notify=False, replace=replace)

    def books_to_merge(self, rows):
        src_books = []
        src_ids = []
        m = self.gui.library_view.model()
        for i, row in enumerate(rows):
            id_ = m.id(row)
            if i == 0:
                dest_id = id_
            else:
                src_ids.append(id_)
                dbfmts = m.db.formats(id_, index_is_id=True)
                if dbfmts:
                    for fmt in dbfmts.split(','):
                        src_books.append(m.db.format_abspath(id_, fmt,
                            index_is_id=True))
        return [dest_id, src_books, src_ids]

    def delete_books_after_merge(self, ids_to_delete):
        self.gui.library_view.model().delete_books_by_id(ids_to_delete)

    def merge_metadata(self, dest_id, src_ids):
        db = self.gui.library_view.model().db
        dest_mi = db.get_metadata(dest_id, index_is_id=True, get_cover=True)
        orig_dest_comments = dest_mi.comments
        for src_id in src_ids:
            src_mi = db.get_metadata(src_id, index_is_id=True, get_cover=True)
            if src_mi.comments and orig_dest_comments != src_mi.comments:
                if not dest_mi.comments:
                    dest_mi.comments = src_mi.comments
                else:
                    dest_mi.comments = unicode(dest_mi.comments) + u'\n\n' + unicode(src_mi.comments)
            if src_mi.title and (not dest_mi.title or
                    dest_mi.title == _('Unknown')):
                dest_mi.title = src_mi.title
            if src_mi.title and (not dest_mi.authors or dest_mi.authors[0] ==
                    _('Unknown')):
                dest_mi.authors = src_mi.authors
                dest_mi.author_sort = src_mi.author_sort
            if src_mi.tags:
                if not dest_mi.tags:
                    dest_mi.tags = src_mi.tags
                else:
                    dest_mi.tags.extend(src_mi.tags)
            if src_mi.cover and not dest_mi.cover:
                dest_mi.cover = src_mi.cover
            if not dest_mi.publisher:
                dest_mi.publisher = src_mi.publisher
            if not dest_mi.rating:
                dest_mi.rating = src_mi.rating
            if not dest_mi.series:
                dest_mi.series = src_mi.series
                dest_mi.series_index = src_mi.series_index
        db.set_metadata(dest_id, dest_mi, ignore_errors=False)

        for key in db.field_metadata: #loop thru all defined fields
          if db.field_metadata[key]['is_custom']:
            colnum = db.field_metadata[key]['colnum']
            # Get orig_dest_comments before it gets changed
            if db.field_metadata[key]['datatype'] == 'comments':
              orig_dest_value = db.get_custom(dest_id, num=colnum, index_is_id=True)
            for src_id in src_ids:
              dest_value = db.get_custom(dest_id, num=colnum, index_is_id=True)
              src_value = db.get_custom(src_id, num=colnum, index_is_id=True)
              if db.field_metadata[key]['datatype'] == 'comments':
                if src_value and src_value != orig_dest_value:
                  if not dest_value:
                    db.set_custom(dest_id, src_value, num=colnum)
                  else:
                    dest_value = unicode(dest_value) + u'\n\n' + unicode(src_value)
                    db.set_custom(dest_id, dest_value, num=colnum)
              if db.field_metadata[key]['datatype'] in \
                ('bool', 'int', 'float', 'rating', 'datetime') \
                and not dest_value:
                db.set_custom(dest_id, src_value, num=colnum)
              if db.field_metadata[key]['datatype'] == 'series' \
                and not dest_value:
                if src_value:
                  src_index = db.get_custom_extra(src_id, num=colnum, index_is_id=True)
                  db.set_custom(dest_id, src_value, num=colnum, extra=src_index)
              if db.field_metadata[key]['datatype'] == 'text' \
                and not db.field_metadata[key]['is_multiple'] \
                and not dest_value:
                db.set_custom(dest_id, src_value, num=colnum)
              if db.field_metadata[key]['datatype'] == 'text' \
                and db.field_metadata[key]['is_multiple']:
                if src_value:
                  if not dest_value:
                    dest_value = src_value
                  else:
                    dest_value.extend(src_value)
                  db.set_custom(dest_id, dest_value, num=colnum)
        # }}}

    def edit_device_collections(self, view, oncard=None):
        model = view.model()
        result = model.get_collections_with_ids()
        d = TagListEditor(self.gui, tag_to_match=None, data=result, key=sort_key)
        d.exec_()
        if d.result() == d.Accepted:
            to_rename = d.to_rename # dict of new text to old ids
            to_delete = d.to_delete # list of ids
            for text in to_rename:
                for old_id in to_rename[text]:
                    model.rename_collection(old_id, new_name=unicode(text))
            for item in to_delete:
                model.delete_collection_using_id(item)
            self.gui.upload_collections(model.db, view=view, oncard=oncard)
            view.reset()

    def apply_metadata_changes(self, id_map,
            title=_('Applying changed metadata'), msg=''):
        self.apply_id_map = list(id_map.iteritems())
        self.apply_current_idx = 0
        self.apply_failures = []
        self.applied_ids = []
        self.apply_pd = None
        if len(self.apply_id_map) > 1:
            from calibre.gui2.dialogs.progress import ProgressDialog
            self.apply_pd = ProgressDialog(title, msg, min=0,
                    max=len(self.apply_id_map)-1, parent=self.gui,
                    cancelable=False)
            self.apply_pd.setModal(True)
            self.apply_pd.show()
        self.do_one_apply()


    def do_one_apply(self):
        if self.apply_current_idx >= len(self.apply_id_map):
            return self.finalize_apply()

        i, mi = self.apply_id_map[self.apply_current_idx]
        db = self.gui.current_db
        try:
            set_title = not mi.is_null('title')
            set_authors = not mi.is_null('authors')
            db.set_metadata(i, mi, commit=False, set_title=set_title,
                    set_authors=set_authors)
            self.applied_ids.append(i)
        except:
            import traceback
            self.apply_failures.append((i, traceback.format_exc()))

        try:
            if mi.cover:
                os.remove(mi.cover)
        except:
            pass

        self.apply_current_idx += 1
        if self.apply_pd is not None:
            self.apply_pd.value += 1
        QTimer.singleShot(50, self.do_one_apply)

    def finalize_apply(self):
        db = self.gui.current_db
        db.commit()

        if self.apply_pd is not None:
            self.apply_pd.hide()

        if self.apply_failures:
            msg = []
            for i, tb in self.apply_failures:
                title = db.title(i, index_is_id=True)
                authors = db.authors(i, index_is_id=True)
                if authors:
                    authors = [x.replace('|', ',') for x in authors.split(',')]
                    title += ' - ' + authors_to_string(authors)
                msg.append(title+'\n\n'+tb+'\n'+('*'*80))

            error_dialog(self.gui, _('Some failures'),
                _('Failed to apply updated metadata for some books'
                    ' in your library. Click "Show Details" to see '
                    'details.'), det_msg='\n\n'.join(msg), show=True)
        if self.applied_ids:
            cr = self.gui.library_view.currentIndex().row()
            self.gui.library_view.model().refresh_ids(
                self.applied_ids, cr)
            if self.gui.cover_flow:
                self.gui.cover_flow.dataChanged()

        self.apply_id_map = []
        self.apply_pd = None

