#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from functools import partial

from PyQt4.Qt import QTableView, Qt, QAbstractItemView, QMenu, pyqtSignal

from calibre.gui2.library.delegates import RatingDelegate, PubDateDelegate, \
    TextDelegate, DateDelegate, TagsDelegate, CcTextDelegate, \
    CcBoolDelegate, CcCommentsDelegate, CcDateDelegate
from calibre.gui2.library.models import BooksModel, DeviceBooksModel
from calibre.utils.config import tweaks
from calibre.gui2 import error_dialog, gprefs
from calibre.gui2.library import DEFAULT_SORT


class BooksView(QTableView): # {{{

    files_dropped = pyqtSignal(object)

    def __init__(self, parent, modelcls=BooksModel):
        QTableView.__init__(self, parent)
        self.rating_delegate = RatingDelegate(self)
        self.timestamp_delegate = DateDelegate(self)
        self.pubdate_delegate = PubDateDelegate(self)
        self.tags_delegate = TagsDelegate(self)
        self.authors_delegate = TextDelegate(self)
        self.series_delegate = TextDelegate(self)
        self.publisher_delegate = TextDelegate(self)
        self.text_delegate = TextDelegate(self)
        self.cc_text_delegate = CcTextDelegate(self)
        self.cc_bool_delegate = CcBoolDelegate(self)
        self.cc_comments_delegate = CcCommentsDelegate(self)
        self.display_parent = parent
        self._model = modelcls(self)
        self.setModel(self._model)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)
        self.selectionModel().currentRowChanged.connect(self._model.current_changed)

        # {{{ Column Header setup
        self.was_restored = False
        self.column_header = self.horizontalHeader()
        self.column_header.setMovable(True)
        self.column_header.sectionMoved.connect(self.save_state)
        self.column_header.setContextMenuPolicy(Qt.CustomContextMenu)
        self.column_header.customContextMenuRequested.connect(self.show_column_header_context_menu)
        # }}}

        self._model.database_changed.connect(self.database_changed)
        hv = self.verticalHeader()
        hv.setClickable(True)
        hv.setCursor(Qt.PointingHandCursor)
        self.selected_ids = []
        self._model.about_to_be_sorted.connect(self.about_to_be_sorted)
        self._model.sorting_done.connect(self.sorting_done)

    # Column Header Context Menu {{{
    def column_header_context_handler(self, action=None, column=None):
        if not action or not column:
            return
        try:
            idx = self.column_map.index(column)
        except:
            return
        h = self.column_header

        if action == 'hide':
            h.setSectionHidden(idx, True)
        elif action == 'show':
            h.setSectionHidden(idx, False)
        elif action == 'ascending':
            self.sortByColumn(idx, Qt.AscendingOrder)
        elif action == 'descending':
            self.sortByColumn(idx, Qt.DescendingOrder)
        elif action == 'defaults':
            self.apply_state(self.get_default_state())
        elif action.startswith('align_'):
            alignment = action.partition('_')[-1]
            self._model.change_alignment(column, alignment)

        self.save_state()

    def show_column_header_context_menu(self, pos):
        idx = self.column_header.logicalIndexAt(pos)
        if idx > -1 and idx < len(self.column_map):
            col = self.column_map[idx]
            name = unicode(self.model().headerData(idx, Qt.Horizontal,
                    Qt.DisplayRole).toString())
            self.column_header_context_menu = QMenu(self)
            if col != 'ondevice':
                self.column_header_context_menu.addAction(_('Hide column %s') %
                        name,
                    partial(self.column_header_context_handler, action='hide',
                        column=col))
            m = self.column_header_context_menu.addMenu(
                    _('Sort on %s')  % name)
            a = m.addAction(_('Ascending'),
                    partial(self.column_header_context_handler,
                        action='ascending', column=col))
            d = m.addAction(_('Descending'),
                    partial(self.column_header_context_handler,
                        action='descending', column=col))
            if self._model.sorted_on[0] == col:
                ac = a if self._model.sorted_on[1] == Qt.AscendingOrder else d
                ac.setCheckable(True)
                ac.setChecked(True)
            m = self.column_header_context_menu.addMenu(
                    _('Change text alignment for %s') % name)
            al = self._model.alignment_map.get(col, 'left')
            for x, t in (('left', _('Left')), ('right', _('Right')), ('center',
                _('Center'))):
                    a = m.addAction(t,
                        partial(self.column_header_context_handler,
                        action='align_'+x, column=col))
                    if al == x:
                        a.setCheckable(True)
                        a.setChecked(True)



            hidden_cols = [self.column_map[i] for i in
                    range(self.column_header.count()) if
                    self.column_header.isSectionHidden(i)]
            try:
                hidden_cols.remove('ondevice')
            except:
                pass
            if hidden_cols:
                self.column_header_context_menu.addSeparator()
                m = self.column_header_context_menu.addMenu(_('Show column'))
                for col in hidden_cols:
                    hidx = self.column_map.index(col)
                    name = unicode(self.model().headerData(hidx, Qt.Horizontal,
                            Qt.DisplayRole).toString())
                    m.addAction(name,
                        partial(self.column_header_context_handler,
                        action='show', column=col))


            self.column_header_context_menu.addSeparator()
            self.column_header_context_menu.addAction(
                    _('Restore default layout'),
                    partial(self.column_header_context_handler,
                        action='defaults', column=col))

            self.column_header_context_menu.popup(self.column_header.mapToGlobal(pos))
    # }}}

    # Sorting {{{
    def about_to_be_sorted(self, idc):
        selected_rows = [r.row() for r in self.selectionModel().selectedRows()]
        self.selected_ids = [idc(r) for r in selected_rows]

    def sorting_done(self, indexc):
        if self.selected_ids:
            indices = [self.model().index(indexc(i), 0) for i in
                    self.selected_ids]
            sm = self.selectionModel()
            for idx in indices:
                sm.select(idx, sm.Select|sm.Rows)
        self.selected_ids = []
    # }}}

    # Ondevice column {{{
    def set_ondevice_column_visibility(self):
        m  = self._model
        self.column_header.setSectionHidden(m.column_map.index('ondevice'),
                not m.device_connected)

    def set_device_connected(self, is_connected):
        self._model.set_device_connected(is_connected)
        self.set_ondevice_column_visibility()
    # }}}

    # Save/Restore State {{{
    def get_state(self):
        h = self.column_header
        cm = self.column_map
        state = {}
        state['hidden_columns'] = [cm[i] for i in  range(h.count())
                if h.isSectionHidden(i) and cm[i] != 'ondevice']
        state['sort_history'] = \
            self.cleanup_sort_history(self.model().sort_history)
        state['column_positions'] = {}
        state['column_sizes'] = {}
        state['column_alignment'] = self._model.alignment_map
        for i in range(h.count()):
            name = cm[i]
            state['column_positions'][name] = h.visualIndex(i)
            if name != 'ondevice':
                state['column_sizes'][name] = h.sectionSize(i)
        return state

    def save_state(self):
        # Only save if we have been initialized (set_database called)
        if len(self.column_map) > 0 and self.was_restored:
            state = self.get_state()
            name = unicode(self.objectName())
            if name:
                gprefs.set(name + ' books view state', state)

    def cleanup_sort_history(self, sort_history):
        history = []
        for col, order in sort_history:
            if col in self.column_map and (not history or history[0][0] != col):
                history.append([col, order])
        return history

    def apply_sort_history(self, saved_history):
        if not saved_history:
            return
        for col, order in reversed(self.cleanup_sort_history(saved_history)[:3]):
            self.sortByColumn(self.column_map.index(col), order)
        #self.model().sort_history = saved_history

    def apply_state(self, state):
        h = self.column_header
        cmap = {}
        hidden = state.get('hidden_columns', [])
        for i, c in enumerate(self.column_map):
            cmap[c] = i
            if c != 'ondevice':
                h.setSectionHidden(i, c in hidden)

        positions = state.get('column_positions', {})
        pmap = {}
        for col, pos in positions.items():
            if col in cmap:
                pmap[pos] = col
        for pos in sorted(pmap.keys()):
            col = pmap[pos]
            idx = cmap[col]
            current_pos = h.visualIndex(idx)
            if current_pos != pos:
                h.moveSection(current_pos, pos)

        sizes = state.get('column_sizes', {})
        for col, size in sizes.items():
            if col in cmap:
                sz = sizes[col]
                if sz < 3:
                    sz = h.sectionSizeHint(cmap[col])
                h.resizeSection(cmap[col], sz)

        self.apply_sort_history(state.get('sort_history', None))

        for col, alignment in state.get('column_alignment', {}).items():
            self._model.change_alignment(col, alignment)

    def get_default_state(self):
        old_state = {
                'hidden_columns': [],
                'sort_history':[DEFAULT_SORT],
                'column_positions': {},
                'column_sizes': {},
                'column_alignment': {
                    'size':'center',
                    'timestamp':'center',
                    'pubdate':'center'},
                }
        h = self.column_header
        cm = self.column_map
        for i in range(h.count()):
            name = cm[i]
            old_state['column_positions'][name] = i
            if name != 'ondevice':
                old_state['column_sizes'][name] = \
                    max(self.sizeHintForColumn(i), h.sectionSizeHint(i))
                if name == 'timestamp':
                    old_state['column_sizes'][name] += 12
        return old_state

    def restore_state(self):
        name = unicode(self.objectName())
        old_state = None
        if name:
            old_state = gprefs.get(name + ' books view state', None)
        if old_state is None:
            old_state = self.get_default_state()

        if tweaks['sort_columns_at_startup'] is not None:
            old_state['sort_history'] = tweaks['sort_columns_at_startup']

        self.apply_state(old_state)
        self.was_restored = True

    # }}}

    # Initialization/Delegate Setup {{{

    def set_database(self, db):
        self.save_state()
        self._model.set_database(db)
        self.tags_delegate.set_database(db)
        self.authors_delegate.set_auto_complete_function(db.all_authors)
        self.series_delegate.set_auto_complete_function(db.all_series)
        self.publisher_delegate.set_auto_complete_function(db.all_publishers)

    def database_changed(self, db):
        for i in range(self.model().columnCount(None)):
            if self.itemDelegateForColumn(i) in (self.rating_delegate,
                    self.timestamp_delegate, self.pubdate_delegate):
                self.setItemDelegateForColumn(i, self.itemDelegate())

        cm = self.column_map

        for colhead in cm:
            if self._model.is_custom_column(colhead):
                cc = self._model.custom_columns[colhead]
                if cc['datatype'] == 'datetime':
                    delegate = CcDateDelegate(self)
                    delegate.set_format(cc['display'].get('date_format',''))
                    self.setItemDelegateForColumn(cm.index(colhead), delegate)
                elif cc['datatype'] == 'comments':
                    self.setItemDelegateForColumn(cm.index(colhead), self.cc_comments_delegate)
                elif cc['datatype'] == 'text':
                    if cc['is_multiple']:
                        self.setItemDelegateForColumn(cm.index(colhead), self.tags_delegate)
                    else:
                        self.setItemDelegateForColumn(cm.index(colhead), self.cc_text_delegate)
                elif cc['datatype'] in ('int', 'float'):
                    self.setItemDelegateForColumn(cm.index(colhead), self.cc_text_delegate)
                elif cc['datatype'] == 'bool':
                    self.setItemDelegateForColumn(cm.index(colhead), self.cc_bool_delegate)
                elif cc['datatype'] == 'rating':
                    self.setItemDelegateForColumn(cm.index(colhead), self.rating_delegate)
            else:
                dattr = colhead+'_delegate'
                delegate = colhead if hasattr(self, dattr) else 'text'
                self.setItemDelegateForColumn(cm.index(colhead), getattr(self,
                    delegate+'_delegate'))

        self.restore_state()
        self.set_ondevice_column_visibility()
        #}}}

    # Context Menu {{{
    def set_context_menu(self, edit_metadata, send_to_device, convert, view,
                         save, open_folder, book_details, delete, similar_menu=None):
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.context_menu = QMenu(self)
        if edit_metadata is not None:
            self.context_menu.addAction(edit_metadata)
        if send_to_device is not None:
            self.context_menu.addAction(send_to_device)
        if convert is not None:
            self.context_menu.addAction(convert)
        self.context_menu.addAction(view)
        self.context_menu.addAction(save)
        if open_folder is not None:
            self.context_menu.addAction(open_folder)
        if delete is not None:
            self.context_menu.addAction(delete)
        if book_details is not None:
            self.context_menu.addAction(book_details)
        if similar_menu is not None:
            self.context_menu.addMenu(similar_menu)

    def contextMenuEvent(self, event):
        self.context_menu.popup(event.globalPos())
        event.accept()
    # }}}

    # Drag 'n Drop {{{
    @classmethod
    def paths_from_event(cls, event):
        '''
        Accept a drop event and return a list of paths that can be read from
        and represent files with extensions.
        '''
        if event.mimeData().hasFormat('text/uri-list'):
            urls = [unicode(u.toLocalFile()) for u in event.mimeData().urls()]
            return [u for u in urls if os.path.splitext(u)[1] and os.access(u, os.R_OK)]

    def dragEnterEvent(self, event):
        if int(event.possibleActions() & Qt.CopyAction) + \
           int(event.possibleActions() & Qt.MoveAction) == 0:
            return
        paths = self.paths_from_event(event)

        if paths:
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        paths = self.paths_from_event(event)
        event.setDropAction(Qt.CopyAction)
        event.accept()
        self.files_dropped.emit(paths)

    # }}}

    @property
    def column_map(self):
        return self._model.column_map

    def scrollContentsBy(self, dx, dy):
        # Needed as Qt bug causes headerview to not always update when scrolling
        QTableView.scrollContentsBy(self, dx, dy)
        if dy != 0:
            self.column_header.update()

    def close(self):
        self._model.close()

    def set_editable(self, editable):
        self._model.set_editable(editable)

    def connect_to_search_box(self, sb, search_done):
        sb.search.connect(self._model.search)
        self._search_done = search_done
        self._model.searched.connect(self.search_done)

    def connect_to_restriction_set(self, tv):
        # must be synchronous (not queued)
        tv.restriction_set.connect(self._model.set_search_restriction)

    def connect_to_book_display(self, bd):
        self._model.new_bookdisplay_data.connect(bd)

    def search_done(self, ok):
        self._search_done(self, ok)

    def row_count(self):
        return self._model.count()

# }}}

class DeviceBooksView(BooksView): # {{{

    def __init__(self, parent):
        BooksView.__init__(self, parent, DeviceBooksModel)
        self.columns_resized = False
        self.resize_on_select = False
        self.rating_delegate = None
        for i in range(10):
            self.setItemDelegateForColumn(i, TextDelegate(self))
        self.setDragDropMode(self.NoDragDrop)
        self.setAcceptDrops(False)

    def set_database(self, db):
        self._model.set_database(db)
        self.restore_state()

    def resizeColumnsToContents(self):
        QTableView.resizeColumnsToContents(self)
        self.columns_resized = True

    def connect_dirtied_signal(self, slot):
        self._model.booklist_dirtied.connect(slot)

    def dropEvent(self, *args):
        error_dialog(self, _('Not allowed'),
        _('Dropping onto a device is not supported. First add the book to the calibre library.')).exec_()

# }}}

