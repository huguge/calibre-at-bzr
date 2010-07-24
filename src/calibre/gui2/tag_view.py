#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Browsing book collection by tags.
'''

from itertools import izip
from functools import partial

from PyQt4.Qt import Qt, QTreeView, QApplication, pyqtSignal, \
                     QFont, QSize, QIcon, QPoint, QVBoxLayout, QComboBox, \
                     QAbstractItemModel, QVariant, QModelIndex, QMenu, \
                     QPushButton, QWidget, QItemDelegate

from calibre.ebooks.metadata import title_sort
from calibre.gui2 import config, NONE
from calibre.library.field_metadata import TagsIcons
from calibre.utils.search_query_parser import saved_searches
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.tag_categories import TagCategories
from calibre.gui2.dialogs.tag_list_editor import TagListEditor
from calibre.gui2.dialogs.edit_authors_dialog import EditAuthorsDialog

class TagDelegate(QItemDelegate): # {{{

    def paint(self, painter, option, index):
        item = index.internalPointer()
        if item.type != TagTreeItem.TAG:
            QItemDelegate.paint(self, painter, option, index)
            return
        r = option.rect
        model = self.parent().model()
        icon = model.data(index, Qt.DecorationRole).toPyObject()
        painter.save()
        if item.tag.state != 0 or not config['show_avg_rating'] or \
                item.tag.avg_rating is None:
            icon.paint(painter, r, Qt.AlignLeft)
        else:
            painter.setOpacity(0.3)
            icon.paint(painter, r, Qt.AlignLeft)
            painter.setOpacity(1)
            rating = item.tag.avg_rating
            painter.setClipRect(r.left(), r.bottom()-int(r.height()*(rating/5.0)),
                    r.width(), r.height())
            icon.paint(painter, r, Qt.AlignLeft)
            painter.setClipRect(r)

        # Paint the text
        r.setLeft(r.left()+r.height()+3)
        painter.drawText(r, Qt.AlignLeft|Qt.AlignVCenter,
                        model.data(index, Qt.DisplayRole).toString())
        painter.restore()

    # }}}

class TagsView(QTreeView): # {{{

    refresh_required    = pyqtSignal()
    tags_marked         = pyqtSignal(object, object)
    user_category_edit  = pyqtSignal(object)
    tag_list_edit       = pyqtSignal(object, object)
    saved_search_edit   = pyqtSignal(object)
    author_sort_edit    = pyqtSignal(object, object)
    tag_item_renamed    = pyqtSignal()
    search_item_renamed = pyqtSignal()

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent=None)
        self.tag_match = None
        self.setUniformRowHeights(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(30, 30))
        self.setTabKeyNavigation(True)
        self.setAlternatingRowColors(True)
        self.setAnimated(True)
        self.setHeaderHidden(True)
        self.setItemDelegate(TagDelegate(self))

    def set_database(self, db, tag_match, sort_by):
        self.hidden_categories = config['tag_browser_hidden_categories']
        self._model = TagsModel(db, parent=self,
                                hidden_categories=self.hidden_categories,
                                search_restriction=None)
        self.sort_by = sort_by
        self.tag_match = tag_match
        self.db = db
        self.search_restriction = None
        self.setModel(self._model)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.clicked.connect(self.toggle)
        self.customContextMenuRequested.connect(self.show_context_menu)
        pop = config['sort_tags_by']
        self.sort_by.setCurrentIndex(self.db.CATEGORY_SORTS.index(pop))
        self.sort_by.currentIndexChanged.connect(self.sort_changed)
        self.refresh_required.connect(self.recount, type=Qt.QueuedConnection)
        db.add_listener(self.database_changed)

    def database_changed(self, event, ids):
        self.refresh_required.emit()

    @property
    def match_all(self):
        return self.tag_match and self.tag_match.currentIndex() > 0

    def sort_changed(self, pop):
        config.set('sort_tags_by', self.db.CATEGORY_SORTS[pop])
        self.recount()

    def set_search_restriction(self, s):
        if s:
            self.search_restriction = s
        else:
            self.search_restriction = None
        self.set_new_model()

    def mouseReleaseEvent(self, event):
        # Swallow everything except leftButton so context menus work correctly
        if event.button() == Qt.LeftButton:
            QTreeView.mouseReleaseEvent(self, event)

    def mouseDoubleClickEvent(self, event):
        # swallow these to avoid toggling and editing at the same time
        pass

    def toggle(self, index):
        modifiers = int(QApplication.keyboardModifiers())
        exclusive = modifiers not in (Qt.CTRL, Qt.SHIFT)
        if self._model.toggle(index, exclusive):
            self.tags_marked.emit(self._model.tokens(), self.match_all)

    def context_menu_handler(self, action=None, category=None,
                             key=None, index=None):
        if not action:
            return
        try:
            if action == 'edit_item':
                self.edit(index)
                return
            if action == 'open_editor':
                self.tag_list_edit.emit(category, key)
                return
            if action == 'manage_categories':
                self.user_category_edit.emit(category)
                return
            if action == 'manage_searches':
                self.saved_search_edit.emit(category)
                return
            if action == 'edit_author_sort':
                self.author_sort_edit.emit(self, index)
                return
            if action == 'hide':
                self.hidden_categories.add(category)
            elif action == 'show':
                self.hidden_categories.discard(category)
            elif action == 'defaults':
                self.hidden_categories.clear()
            config.set('tag_browser_hidden_categories', self.hidden_categories)
            self.set_new_model()
        except:
            return

    def show_context_menu(self, point):
        index = self.indexAt(point)
        if not index.isValid():
            return False
        item = index.internalPointer()
        tag_name = ''
        if item.type == TagTreeItem.TAG:
            tag_item = item
            tag_name = item.tag.name
            tag_id = item.tag.id
            item = item.parent
        if item.type == TagTreeItem.CATEGORY:
            category = unicode(item.name.toString())
            key = item.category_key
            # Verify that we are working with a field that we know something about
            if key not in self.db.field_metadata:
                return True

            self.context_menu = QMenu(self)
            # If the user right-clicked on an editable item, then offer
            # the possibility of renaming that item
            if tag_name and \
                    (key in ['authors', 'tags', 'series', 'publisher', 'search'] or \
                     self.db.field_metadata[key]['is_custom'] and \
                     self.db.field_metadata[key]['datatype'] != 'rating'):
                self.context_menu.addAction(_('Rename \'%s\'')%tag_name,
                        partial(self.context_menu_handler, action='edit_item',
                                category=tag_item, index=index))
                if key == 'authors':
                    self.context_menu.addAction(_('Edit sort for \'%s\'')%tag_name,
                            partial(self.context_menu_handler,
                                    action='edit_author_sort', index=tag_id))
                self.context_menu.addSeparator()
            # Hide/Show/Restore categories
            self.context_menu.addAction(_('Hide category %s') % category,
                partial(self.context_menu_handler, action='hide', category=category))
            if self.hidden_categories:
                m = self.context_menu.addMenu(_('Show category'))
                for col in sorted(self.hidden_categories, cmp=lambda x,y: cmp(x.lower(), y.lower())):
                    m.addAction(col,
                        partial(self.context_menu_handler, action='show', category=col))
                self.context_menu.addAction(_('Show all categories'),
                            partial(self.context_menu_handler, action='defaults'))

            # Offer specific editors for tags/series/publishers/saved searches
            self.context_menu.addSeparator()
            if key in ['tags', 'publisher', 'series'] or \
                        self.db.field_metadata[key]['is_custom']:
                self.context_menu.addAction(_('Manage %s')%category,
                        partial(self.context_menu_handler, action='open_editor',
                                category=tag_name, key=key))
            elif key == 'authors':
                self.context_menu.addAction(_('Manage %s')%category,
                        partial(self.context_menu_handler, action='edit_author_sort'))
            elif key == 'search':
                self.context_menu.addAction(_('Manage Saved Searches'),
                    partial(self.context_menu_handler, action='manage_searches',
                            category=tag_name))

            # Always show the user categories editor
            self.context_menu.addSeparator()
            if category in self.db.prefs.get('user_categories', {}).keys():
                self.context_menu.addAction(_('Manage User Categories'),
                        partial(self.context_menu_handler, action='manage_categories',
                                category=category))
            else:
                self.context_menu.addAction(_('Manage User Categories'),
                        partial(self.context_menu_handler, action='manage_categories',
                                category=None))

            self.context_menu.popup(self.mapToGlobal(point))
        return True

    def clear(self):
        if self.model():
            self.model().clear_state()

    def is_visible(self, idx):
        item = idx.internalPointer()
        if getattr(item, 'type', None) == TagTreeItem.TAG:
            idx = idx.parent()
        return self.isExpanded(idx)

    def recount(self, *args):
        ci = self.currentIndex()
        if not ci.isValid():
            ci = self.indexAt(QPoint(10, 10))
        path = self.model().path_for_index(ci) if self.is_visible(ci) else None
        try:
            if not self.model().refresh(): # categories changed!
                self.set_new_model()
                path = None
        except: #Database connection could be closed if an integrity check is happening
            pass
        if path:
            idx = self.model().index_for_path(path)
            if idx.isValid():
                self.setCurrentIndex(idx)
                self.scrollTo(idx, QTreeView.PositionAtCenter)

    # If the number of user categories changed,  if custom columns have come or
    # gone, or if columns have been hidden or restored, we must rebuild the
    # model. Reason: it is much easier than reconstructing the browser tree.
    def set_new_model(self):
        try:
            self._model = TagsModel(self.db, parent=self,
                                    hidden_categories=self.hidden_categories,
                                    search_restriction=self.search_restriction)
            self.setModel(self._model)
        except:
            # The DB must be gone. Set the model to None and hope that someone
            # will call set_database later. I don't know if this in fact works
            self._model = None
            self.setModel(None)
    # }}}

class TagTreeItem(object): # {{{

    CATEGORY = 0
    TAG      = 1
    ROOT     = 2

    def __init__(self, data=None, category_icon=None, icon_map=None,
                 parent=None, tooltip=None, category_key=None):
        self.parent = parent
        self.children = []
        if self.parent is not None:
            self.parent.append(self)
        if data is None:
            self.type = self.ROOT
        else:
            self.type = self.TAG if category_icon is None else self.CATEGORY
        if self.type == self.CATEGORY:
            self.name, self.icon = map(QVariant, (data, category_icon))
            self.py_name = data
            self.bold_font = QFont()
            self.bold_font.setBold(True)
            self.bold_font = QVariant(self.bold_font)
            self.category_key = category_key
        elif self.type == self.TAG:
            icon_map[0] = data.icon
            self.tag, self.icon_state_map = data, list(map(QVariant, icon_map))
        self.tooltip = tooltip

    def __str__(self):
        if self.type == self.ROOT:
            return 'ROOT'
        if self.type == self.CATEGORY:
            return 'CATEGORY:'+str(QVariant.toString(self.name))+':%d'%len(self.children)
        return 'TAG:'+self.tag.name

    def row(self):
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0

    def append(self, child):
        child.parent = self
        self.children.append(child)

    def data(self, role):
        if self.type == self.TAG:
            return self.tag_data(role)
        if self.type == self.CATEGORY:
            return self.category_data(role)
        return NONE

    def category_data(self, role):
        if role == Qt.DisplayRole:
            return QVariant(self.py_name + ' [%d]'%len(self.children))
        if role == Qt.DecorationRole:
            return self.icon
        if role == Qt.FontRole:
            return self.bold_font
        if role == Qt.ToolTipRole and self.tooltip is not None:
            return QVariant(self.tooltip)
        return NONE

    def tag_data(self, role):
        if role == Qt.DisplayRole:
            if self.tag.count == 0:
                return QVariant('%s'%(self.tag.name))
            else:
                return QVariant('[%d] %s'%(self.tag.count, self.tag.name))
        if role == Qt.EditRole:
            return QVariant(self.tag.name)
        if role == Qt.DecorationRole:
            return self.icon_state_map[self.tag.state]
        if role == Qt.ToolTipRole and self.tag.tooltip is not None:
            return QVariant(self.tag.tooltip)
        return NONE

    def toggle(self):
        if self.type == self.TAG:
            self.tag.state = (self.tag.state + 1)%3

    # }}}

class TagsModel(QAbstractItemModel): # {{{

    def __init__(self, db, parent, hidden_categories=None, search_restriction=None):
        QAbstractItemModel.__init__(self, parent)

        # must do this here because 'QPixmap: Must construct a QApplication
        # before a QPaintDevice'. The ':' in front avoids polluting either the
        # user-defined categories (':' at end) or columns namespaces (no ':').
        self.category_icon_map = TagsIcons({
                    'authors'   : QIcon(I('user_profile.svg')),
                    'series'    : QIcon(I('series.svg')),
                    'formats'   : QIcon(I('book.svg')),
                    'publisher' : QIcon(I('publisher.png')),
                    'rating'    : QIcon(I('star.png')),
                    'news'      : QIcon(I('news.svg')),
                    'tags'      : QIcon(I('tags.svg')),
                    ':custom'   : QIcon(I('column.svg')),
                    ':user'     : QIcon(I('drawer.svg')),
                    'search'    : QIcon(I('search.svg'))})
        self.categories_with_ratings = ['authors', 'series', 'publisher', 'tags']

        self.icon_state_map = [None, QIcon(I('plus.svg')), QIcon(I('minus.svg'))]
        self.db = db
        self.tags_view = parent
        self.hidden_categories = hidden_categories
        self.search_restriction = search_restriction
        self.row_map = []

        # get_node_tree cannot return None here, because row_map is empty
        data = self.get_node_tree(config['sort_tags_by'])
        self.root_item = TagTreeItem()
        for i, r in enumerate(self.row_map):
            if self.hidden_categories and self.categories[i] in self.hidden_categories:
                continue
            if self.db.field_metadata[r]['kind'] != 'user':
                tt = _('The lookup/search name is "{0}"').format(r)
            else:
                tt = ''
            c = TagTreeItem(parent=self.root_item,
                    data=self.categories[i],
                    category_icon=self.category_icon_map[r],
                    tooltip=tt, category_key=r)
            # This duplicates code in refresh(). Having it here as well
            # can save seconds during startup, because we avoid a second
            # call to get_node_tree.
            for tag in data[r]:
                if r not in self.categories_with_ratings and \
                            not self.db.field_metadata[r]['is_custom'] and \
                            not self.db.field_metadata[r]['kind'] == 'user':
                    tag.avg_rating = None
                TagTreeItem(parent=c, data=tag, icon_map=self.icon_state_map)

    def set_search_restriction(self, s):
        self.search_restriction = s

    def get_node_tree(self, sort):
        old_row_map = self.row_map[:]
        self.row_map = []
        self.categories = []

        # Reconstruct the user categories, putting them into metadata
        tb_cats = self.db.field_metadata
        for k in tb_cats.keys():
            if tb_cats[k]['kind'] in ['user', 'search']:
                del tb_cats[k]
        for user_cat in sorted(self.db.prefs.get('user_categories', {}).keys()):
            cat_name = user_cat+':' # add the ':' to avoid name collision
            tb_cats.add_user_category(label=cat_name, name=user_cat)
        if len(saved_searches().names()):
            tb_cats.add_search_category(label='search', name=_('Searches'))

        # Now get the categories
        if self.search_restriction:
            data = self.db.get_categories(sort=sort,
                        icon_map=self.category_icon_map,
                        ids=self.db.search('', return_matches=True))
        else:
            data = self.db.get_categories(sort=sort, icon_map=self.category_icon_map)

        tb_categories = self.db.field_metadata
        for category in tb_categories:
            if category in data: # The search category can come and go
                self.row_map.append(category)
                self.categories.append(tb_categories[category]['name'])
        if len(old_row_map) != 0 and len(old_row_map) != len(self.row_map):
            # A category has been added or removed. We must force a rebuild of
            # the model
            return None
        return data

    def refresh(self):
        data = self.get_node_tree(config['sort_tags_by']) # get category data
        if data is None:
            return False
        row_index = -1
        for i, r in enumerate(self.row_map):
            if self.hidden_categories and self.categories[i] in self.hidden_categories:
                continue
            row_index += 1
            category = self.root_item.children[row_index]
            names = [t.tag.name for t in category.children]
            states = [t.tag.state for t in category.children]
            state_map = dict(izip(names, states))
            category_index = self.index(row_index, 0, QModelIndex())
            if len(category.children) > 0:
                self.beginRemoveRows(category_index, 0,
                        len(category.children)-1)
                category.children = []
                self.endRemoveRows()
            if len(data[r]) > 0:
                self.beginInsertRows(category_index, 0, len(data[r])-1)
                for tag in data[r]:
                    if r not in self.categories_with_ratings and \
                                not self.db.field_metadata[r]['is_custom'] and \
                                not self.db.field_metadata[r]['kind'] == 'user':
                        tag.avg_rating = None
                    tag.state = state_map.get(tag.name, 0)
                    t = TagTreeItem(parent=category, data=tag, icon_map=self.icon_state_map)
                self.endInsertRows()
        return True

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if not index.isValid():
            return NONE
        item = index.internalPointer()
        return item.data(role)

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return NONE
        # set up to position at the category label
        path = self.path_for_index(self.parent(index))
        val = unicode(value.toString())
        if not val:
            error_dialog(self.tags_view, _('Item is blank'),
                        _('An item cannot be set to nothing. Delete it instead.')).exec_()
            return False
        item = index.internalPointer()
        key = item.parent.category_key
        # make certain we know about the item's category
        if key not in self.db.field_metadata:
            return
        if key == 'search':
            if val in saved_searches().names():
                error_dialog(self.tags_view, _('Duplicate search name'),
                    _('The saved search name %s is already used.')%val).exec_()
                return False
            saved_searches().rename(unicode(item.data(role).toString()), val)
            self.tags_view.search_item_renamed.emit()
        else:
            if key == 'series':
                self.db.rename_series(item.tag.id, val)
            elif key == 'publisher':
                self.db.rename_publisher(item.tag.id, val)
            elif key == 'tags':
                self.db.rename_tag(item.tag.id, val)
            elif key == 'authors':
                self.db.rename_author(item.tag.id, val)
            elif self.db.field_metadata[key]['is_custom']:
                self.db.rename_custom_item(item.tag.id, val,
                                    label=self.db.field_metadata[key]['label'])
            self.tags_view.tag_item_renamed.emit()
        item.tag.name = val
        self.refresh() # Should work, because no categories can have disappeared
        if path:
            idx = self.index_for_path(path)
            if idx.isValid():
                self.tags_view.setCurrentIndex(idx)
                self.tags_view.scrollTo(idx, QTreeView.PositionAtCenter)
        return True

    def headerData(self, *args):
        return NONE

    def flags(self, *args):
        return Qt.ItemIsEnabled|Qt.ItemIsSelectable|Qt.ItemIsEditable

    def path_for_index(self, index):
        ans = []
        while index.isValid():
            ans.append(index.row())
            index = self.parent(index)
        ans.reverse()
        return ans

    def index_for_path(self, path):
        parent = QModelIndex()
        for i in path:
            parent = self.index(i, 0, parent)
            if not parent.isValid():
                return QModelIndex()
        return parent

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        try:
            child_item = parent_item.children[row]
        except IndexError:
            return QModelIndex()

        ans = self.createIndex(row, column, child_item)
        return ans

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        child_item = index.internalPointer()
        parent_item = getattr(child_item, 'parent', None)

        if parent_item is self.root_item or parent_item is None:
            return QModelIndex()

        ans = self.createIndex(parent_item.row(), 0, parent_item)
        return ans

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        return len(parent_item.children)

    def reset_all_states(self, except_=None):
        update_list = []
        for i in xrange(self.rowCount(QModelIndex())):
            category_index = self.index(i, 0, QModelIndex())
            for j in xrange(self.rowCount(category_index)):
                tag_index = self.index(j, 0, category_index)
                tag_item = tag_index.internalPointer()
                tag = tag_item.tag
                if tag is except_:
                    self.dataChanged.emit(tag_index, tag_index)
                    continue
                if tag.state != 0 or tag in update_list:
                    tag.state = 0
                    update_list.append(tag)
                    self.dataChanged.emit(tag_index, tag_index)

    def clear_state(self):
        self.reset_all_states()

    def toggle(self, index, exclusive):
        if not index.isValid(): return False
        item = index.internalPointer()
        if item.type == TagTreeItem.TAG:
            item.toggle()
            if exclusive:
                self.reset_all_states(except_=item.tag)
            self.dataChanged.emit(index, index)
            return True
        return False

    def tokens(self):
        ans = []
        tags_seen = set()
        row_index = -1
        for i, key in enumerate(self.row_map):
            if self.hidden_categories and self.categories[i] in self.hidden_categories:
                continue
            row_index += 1
            if key.endswith(':'): # User category, so skip it. The tag will be marked in its real category
                continue
            category_item = self.root_item.children[row_index]
            for tag_item in category_item.children:
                tag = tag_item.tag
                if tag.state > 0:
                    prefix = ' not ' if tag.state == 2 else ''
                    category = key if key != 'news' else 'tag'
                    if tag.name and tag.name[0] == u'\u2605': # char is a star. Assume rating
                        ans.append('%s%s:%s'%(prefix, category, len(tag.name)))
                    else:
                        if category == 'tags':
                            if tag.name in tags_seen:
                                continue
                            tags_seen.add(tag.name)
                        ans.append('%s%s:"=%s"'%(prefix, category, tag.name))
        return ans

    # }}}

class TagBrowserMixin(object): # {{{

    def __init__(self, db):
        self.library_view.model().count_changed_signal.connect(self.tags_view.recount)
        self.tags_view.set_database(self.library_view.model().db,
                self.tag_match, self.sort_by)
        self.tags_view.tags_marked.connect(self.search.search_from_tags)
        self.tags_view.tags_marked.connect(self.saved_search.clear_to_help)
        self.tags_view.tag_list_edit.connect(self.do_tags_list_edit)
        self.tags_view.user_category_edit.connect(self.do_user_categories_edit)
        self.tags_view.saved_search_edit.connect(self.do_saved_search_edit)
        self.tags_view.author_sort_edit.connect(self.do_author_sort_edit)
        self.tags_view.tag_item_renamed.connect(self.do_tag_item_renamed)
        self.tags_view.search_item_renamed.connect(self.saved_search.clear_to_help)
        self.edit_categories.clicked.connect(lambda x:
                self.do_user_categories_edit())

    def do_user_categories_edit(self, on_category=None):
        d = TagCategories(self, self.library_view.model().db, on_category)
        d.exec_()
        if d.result() == d.Accepted:
            self.tags_view.set_new_model()
            self.tags_view.recount()

    def do_tags_list_edit(self, tag, category):
        db=self.library_view.model().db
        if category == 'tags':
            result = db.get_tags_with_ids()
            compare = (lambda x,y:cmp(x.lower(), y.lower()))
        elif category == 'series':
            result = db.get_series_with_ids()
            compare = (lambda x,y:cmp(title_sort(x).lower(), title_sort(y).lower()))
        elif category == 'publisher':
            result = db.get_publishers_with_ids()
            compare = (lambda x,y:cmp(x.lower(), y.lower()))
        else: # should be a custom field
            cc_label = None
            if category in db.field_metadata:
                cc_label = db.field_metadata[category]['label']
                result = self.db.get_custom_items_with_ids(label=cc_label)
            else:
                result = []
            compare = (lambda x,y:cmp(x.lower(), y.lower()))

        d = TagListEditor(self, tag_to_match=tag, data=result, compare=compare)
        d.exec_()
        if d.result() == d.Accepted:
            to_rename = d.to_rename # dict of new text to old id
            to_delete = d.to_delete # list of ids
            rename_func = None
            if category == 'tags':
                rename_func = db.rename_tag
                delete_func = db.delete_tag_using_id
            elif category == 'series':
                rename_func = db.rename_series
                delete_func = db.delete_series_using_id
            elif category == 'publisher':
                rename_func = db.rename_publisher
                delete_func = db.delete_publisher_using_id
            else:
                rename_func = partial(db.rename_custom_item, label=cc_label)
                delete_func = partial(db.delete_custom_item_using_id, label=cc_label)
            if rename_func:
                for text in to_rename:
                        for old_id in to_rename[text]:
                            rename_func(old_id, new_name=unicode(text))
                for item in to_delete:
                    delete_func(item)

            # Clean up everything, as information could have changed for many books.
            self.library_view.model().refresh()
            self.tags_view.set_new_model()
            self.tags_view.recount()
            self.saved_search.clear_to_help()
            self.search.clear_to_help()

    def do_tag_item_renamed(self):
        # Clean up library view and search
        self.library_view.model().refresh()
        self.saved_search.clear_to_help()
        self.search.clear_to_help()

    def do_author_sort_edit(self, parent, id):
        db = self.library_view.model().db
        editor = EditAuthorsDialog(parent, db, id)
        d = editor.exec_()
        if d:
            for (id, old_author, new_author, new_sort) in editor.result:
                if old_author != new_author:
                    # The id might change if the new author already exists
                    id = db.rename_author(id, new_author)
                db.set_sort_field_for_author(id, unicode(new_sort))
            self.library_view.model().refresh()
            self.tags_view.recount()

# }}}

class TagBrowserWidget(QWidget): # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        parent.tags_view = TagsView(parent)
        self._layout.addWidget(parent.tags_view)

        parent.sort_by = QComboBox(parent)
        # Must be in the same order as db2.CATEGORY_SORTS
        for x in (_('Sort by name'), _('Sort by popularity'),
                  _('Sort by average rating')):
            parent.sort_by.addItem(x)
        parent.sort_by.setToolTip(
                _('Set the sort order for entries in the Tag Browser'))
        parent.sort_by.setStatusTip(parent.sort_by.toolTip())
        parent.sort_by.setCurrentIndex(0)
        self._layout.addWidget(parent.sort_by)

        parent.tag_match = QComboBox(parent)
        for x in (_('Match any'), _('Match all')):
            parent.tag_match.addItem(x)
        parent.tag_match.setCurrentIndex(0)
        self._layout.addWidget(parent.tag_match)
        parent.tag_match.setToolTip(
                _('When selecting multiple entries in the Tag Browser '
                    'match any or all of them'))
        parent.tag_match.setStatusTip(parent.tag_match.toolTip())

        parent.edit_categories = QPushButton(_('Manage &user categories'), parent)
        self._layout.addWidget(parent.edit_categories)
        parent.edit_categories.setToolTip(
                _('Add your own categories to the Tag Browser'))
        parent.edit_categories.setStatusTip(parent.edit_categories.toolTip())


# }}}

