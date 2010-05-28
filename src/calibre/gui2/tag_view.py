#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Browsing book collection by tags.
'''

from itertools import izip

from PyQt4.Qt import Qt, QTreeView, QApplication, pyqtSignal, \
                     QFont, QSize, QIcon, QPoint, \
                     QAbstractItemModel, QVariant, QModelIndex
from calibre.gui2 import config, NONE
from calibre.utils.config import prefs
from calibre.library.field_metadata import TagsIcons
from calibre.utils.search_query_parser import saved_searches

class TagsView(QTreeView): # {{{

    need_refresh    = pyqtSignal()
    restriction_set = pyqtSignal(object)
    tags_marked     = pyqtSignal(object, object)

    def __init__(self, *args):
        QTreeView.__init__(self, *args)
        self.setUniformRowHeights(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(30, 30))
        self.tag_match = None

    def set_database(self, db, tag_match, popularity, restriction):
        self._model = TagsModel(db, parent=self)
        self.popularity = popularity
        self.restriction = restriction
        self.tag_match = tag_match
        self.db = db
        self.setModel(self._model)
        self.clicked.connect(self.toggle)
        self.popularity.setChecked(config['sort_by_popularity'])
        self.popularity.stateChanged.connect(self.sort_changed)
        self.restriction.activated[str].connect(self.search_restriction_set)
        self.need_refresh.connect(self.recount, type=Qt.QueuedConnection)
        db.add_listener(self.database_changed)
        self.saved_searches_changed(recount=False)

    def create_tag_category(self, name, tag_list):
        self._model.create_tag_category(name, tag_list)
        self.recount()

    def database_changed(self, event, ids):
        self.need_refresh.emit()

    @property
    def match_all(self):
        return self.tag_match and self.tag_match.currentIndex() > 0

    def sort_changed(self, state):
        config.set('sort_by_popularity', state == Qt.Checked)
        self.model().refresh()
        # self.search_restriction_set()

    def search_restriction_set(self, s):
        self.clear()
        if len(s) == 0:
            self.search_restriction = ''
        else:
            self.search_restriction = 'search:"%s"' % unicode(s).strip()
        self.model().set_search_restriction(self.search_restriction)
        self.restriction_set.emit(self.search_restriction)
        self.recount() # Must happen after the emission of the restriction_set signal
        self.tags_marked.emit(self._model.tokens(), self.match_all)

    def toggle(self, index):
        modifiers = int(QApplication.keyboardModifiers())
        exclusive = modifiers not in (Qt.CTRL, Qt.SHIFT)
        if self._model.toggle(index, exclusive):
            self.tags_marked.emit(self._model.tokens(), self.match_all)

    def clear(self):
        self.model().clear_state()

    def saved_searches_changed(self, recount=True):
        p = prefs['saved_searches'].keys()
        p.sort()
        t = self.restriction.currentText()
        self.restriction.clear() # rebuild the restrictions combobox using current saved searches
        self.restriction.addItem('')
        for s in p:
            self.restriction.addItem(s)
        if t in p: # redo the current restriction, if there was one
            self.restriction.setCurrentIndex(self.restriction.findText(t))
            self.search_restriction_set(t)
        if recount:
            self.recount()

    def recount(self, *args):
        ci = self.currentIndex()
        if not ci.isValid():
            ci = self.indexAt(QPoint(10, 10))
        path = self.model().path_for_index(ci)
        try:
            self.model().refresh()
        except: #Database connection could be closed if an integrity check is happening
            pass
        if path:
            idx = self.model().index_for_path(path)
            if idx.isValid():
                self.setCurrentIndex(idx)
                self.scrollTo(idx, QTreeView.PositionAtCenter)

    '''
    If the number of user categories changed, or if custom columns have come or gone,
    we must rebuild the model. Reason: it is much easier to do that than to reconstruct
    the browser tree.
    '''
    def set_new_model(self):
        self._model = TagsModel(self.db, parent=self)
        self.setModel(self._model)
    # }}}

class TagTreeItem(object): # {{{

    CATEGORY = 0
    TAG      = 1
    ROOT     = 2

    def __init__(self, data=None, category_icon=None, icon_map=None, parent=None, tooltip=None):
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

    def __init__(self, db, parent=None):
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

        self.icon_state_map = [None, QIcon(I('plus.svg')), QIcon(I('minus.svg'))]
        self.db = db
        self.search_restriction = ''
        self.ignore_next_search = 0

        # Reconstruct the user categories, putting them into metadata
        tb_cats = self.db.field_metadata
        for k in tb_cats.keys():
            if tb_cats[k]['kind'] in ['user', 'search']:
                del tb_cats[k]
        for user_cat in sorted(prefs['user_categories'].keys()):
            cat_name = user_cat+':' # add the ':' to avoid name collision
            tb_cats.add_user_category(label=cat_name, name=user_cat)
        if len(saved_searches.names()):
            tb_cats.add_search_category(label='search', name=_('Searches'))

        data = self.get_node_tree(config['sort_by_popularity'])
        self.root_item = TagTreeItem()
        for i, r in enumerate(self.row_map):
            if self.db.field_metadata[r]['kind'] != 'user':
                tt = _('The lookup/search name is "{0}"').format(r)
            else:
                tt = ''
            c = TagTreeItem(parent=self.root_item,
                    data=self.categories[i],
                    category_icon=self.category_icon_map[r],
                    tooltip=tt)
            for tag in data[r]:
                TagTreeItem(parent=c, data=tag, icon_map=self.icon_state_map)

    def set_search_restriction(self, s):
        self.search_restriction = s

    def get_node_tree(self, sort):
        self.row_map = []
        self.categories = []

        if len(self.search_restriction):
            data = self.db.get_categories(sort_on_count=sort, icon_map=self.category_icon_map,
                        ids=self.db.search(self.search_restriction, return_matches=True))
        else:
            data = self.db.get_categories(sort_on_count=sort, icon_map=self.category_icon_map)

        tb_categories = self.db.field_metadata
        for category in tb_categories:
            if category in data: # They should always be there, but ...
                self.row_map.append(category)
                self.categories.append(tb_categories[category]['name'])

        return data

    def refresh(self):
        data = self.get_node_tree(config['sort_by_popularity']) # get category data
        for i, r in enumerate(self.row_map):
            category = self.root_item.children[i]
            names = [t.tag.name for t in category.children]
            states = [t.tag.state for t in category.children]
            state_map = dict(izip(names, states))
            category_index = self.index(i, 0, QModelIndex())
            if len(category.children) > 0:
                self.beginRemoveRows(category_index, 0,
                        len(category.children)-1)
                category.children = []
                self.endRemoveRows()
            if len(data[r]) > 0:
                self.beginInsertRows(category_index, 0, len(data[r])-1)
                for tag in data[r]:
                    tag.state = state_map.get(tag.name, 0)
                    t = TagTreeItem(parent=category, data=tag, icon_map=self.icon_state_map)
                self.endInsertRows()

    def columnCount(self, parent):
        return 1

    def data(self, index, role):
        if not index.isValid():
            return NONE
        item = index.internalPointer()
        return item.data(role)

    def headerData(self, *args):
        return NONE

    def flags(self, *args):
        return Qt.ItemIsEnabled|Qt.ItemIsSelectable

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

    def reinit(self, *args, **kwargs):
        if self.ignore_next_search == 0:
            self.reset_all_states()
        else:
            self.ignore_next_search -= 1

    def toggle(self, index, exclusive):
        if not index.isValid(): return False
        item = index.internalPointer()
        if item.type == TagTreeItem.TAG:
            item.toggle()
            if exclusive:
                self.reset_all_states(except_=item.tag)
            self.ignore_next_search = 2
            self.dataChanged.emit(index, index)
            return True
        return False

    def tokens(self):
        ans = []
        tags_seen = set()
        for i, key in enumerate(self.row_map):
            if key.endswith(':'): # User category, so skip it. The tag will be marked in its real category
                continue
            category_item = self.root_item.children[i]
            for tag_item in category_item.children:
                tag = tag_item.tag
                if tag.state > 0:
                    prefix = ' not ' if tag.state == 2 else ''
                    category = key if key != 'news' else 'tag'
                    if tag.name[0] == u'\u2605': # char is a star. Assume rating
                        ans.append('%s%s:%s'%(prefix, category, len(tag.name)))
                    else:
                        if category == 'tags':
                            if tag.name in tags_seen:
                                continue
                            tags_seen.add(tag.name)
                        ans.append('%s%s:"=%s"'%(prefix, category, tag.name))
        return ans

    # }}}

