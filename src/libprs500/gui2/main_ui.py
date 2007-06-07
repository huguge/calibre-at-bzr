# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'main.ui'
#
# Created: Wed Jun  6 19:26:17 2007
#      by: PyQt4 UI code generator 4-snapshot-20070530
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(QtCore.QSize(QtCore.QRect(0,0,777,822).size()).expandedTo(MainWindow.minimumSizeHint()))

        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred,QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(MainWindow.sizePolicy().hasHeightForWidth())
        MainWindow.setSizePolicy(sizePolicy)
        MainWindow.setWindowIcon(QtGui.QIcon(":/library"))

        self.centralwidget = QtGui.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.gridlayout = QtGui.QGridLayout(self.centralwidget)
        self.gridlayout.setObjectName("gridlayout")

        self.hboxlayout = QtGui.QHBoxLayout()
        self.hboxlayout.setSpacing(6)






        self.device_tree = DeviceView(self.centralwidget)

        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred,QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.device_tree.sizePolicy().hasHeightForWidth())
        self.device_tree.setSizePolicy(sizePolicy)
        self.device_tree.setMaximumSize(QtCore.QSize(10000,90))
        self.device_tree.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.device_tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.device_tree.setDragDropMode(QtGui.QAbstractItemView.DragDrop)
        self.device_tree.setFlow(QtGui.QListView.TopToBottom)
        self.device_tree.setSpacing(20)
        self.device_tree.setViewMode(QtGui.QListView.IconMode)
        self.device_tree.setObjectName("device_tree")
        self.hboxlayout.addWidget(self.device_tree)

        self.df = QtGui.QLabel(self.centralwidget)

        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred,QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.df.sizePolicy().hasHeightForWidth())
        self.df.setSizePolicy(sizePolicy)
        self.df.setMaximumSize(QtCore.QSize(16777215,90))
        self.df.setTextFormat(QtCore.Qt.RichText)
        self.df.setOpenExternalLinks(True)
        self.df.setObjectName("df")
        self.hboxlayout.addWidget(self.df)
        self.gridlayout.addLayout(self.hboxlayout,0,0,1,1)

        self.hboxlayout1 = QtGui.QHBoxLayout()
        self.hboxlayout1.setSpacing(6)




        self.hboxlayout1.setObjectName("hboxlayout1")

        self.label = QtGui.QLabel(self.centralwidget)
        self.label.setObjectName("label")
        self.hboxlayout1.addWidget(self.label)

        self.search = SearchBox(self.centralwidget)
        self.search.setEnabled(True)
        self.search.setAcceptDrops(False)
        self.search.setAutoFillBackground(False)
        self.search.setFrame(True)
        self.search.setObjectName("search")
        self.hboxlayout1.addWidget(self.search)

        self.clear_button = QtGui.QToolButton(self.centralwidget)
        self.clear_button.setIcon(QtGui.QIcon(":/images/clear.png"))
        self.clear_button.setObjectName("clear_button")
        self.hboxlayout1.addWidget(self.clear_button)
        self.gridlayout.addLayout(self.hboxlayout1,1,0,1,1)

        self.tabs = AnimatedTabWidget(self.centralwidget)
        self.tabs.setTabPosition(QtGui.QTabWidget.West)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setObjectName("tabs")

        self.books_tab = QtGui.QWidget()
        self.books_tab.setObjectName("books_tab")

        self.gridlayout1 = QtGui.QGridLayout(self.books_tab)
        self.gridlayout1.setObjectName("gridlayout1")

        self.stacks = QtGui.QStackedWidget(self.books_tab)

        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(100)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.stacks.sizePolicy().hasHeightForWidth())
        self.stacks.setSizePolicy(sizePolicy)
        self.stacks.setObjectName("stacks")

        self.library = QtGui.QWidget()
        self.library.setObjectName("library")

        self.gridlayout2 = QtGui.QGridLayout(self.library)
        self.gridlayout2.setObjectName("gridlayout2")

        self.library_view = BooksView(self.library)

        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(100)
        sizePolicy.setVerticalStretch(10)
        sizePolicy.setHeightForWidth(self.library_view.sizePolicy().hasHeightForWidth())
        self.library_view.setSizePolicy(sizePolicy)
        self.library_view.setAcceptDrops(True)
        self.library_view.setDragEnabled(True)
        self.library_view.setDragDropOverwriteMode(False)
        self.library_view.setDragDropMode(QtGui.QAbstractItemView.DragDrop)
        self.library_view.setAlternatingRowColors(True)
        self.library_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.library_view.setShowGrid(False)
        self.library_view.setObjectName("library_view")
        self.gridlayout2.addWidget(self.library_view,0,0,1,1)
        self.stacks.addWidget(self.library)

        self.main_memory = QtGui.QWidget()
        self.main_memory.setObjectName("main_memory")

        self.gridlayout3 = QtGui.QGridLayout(self.main_memory)
        self.gridlayout3.setObjectName("gridlayout3")

        self.main_memory_view = BooksView(self.main_memory)

        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(100)
        sizePolicy.setVerticalStretch(10)
        sizePolicy.setHeightForWidth(self.main_memory_view.sizePolicy().hasHeightForWidth())
        self.main_memory_view.setSizePolicy(sizePolicy)
        self.main_memory_view.setAcceptDrops(True)
        self.main_memory_view.setDragEnabled(True)
        self.main_memory_view.setDragDropOverwriteMode(False)
        self.main_memory_view.setDragDropMode(QtGui.QAbstractItemView.DragDrop)
        self.main_memory_view.setAlternatingRowColors(True)
        self.main_memory_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.main_memory_view.setShowGrid(False)
        self.main_memory_view.setObjectName("main_memory_view")
        self.gridlayout3.addWidget(self.main_memory_view,0,0,1,1)
        self.stacks.addWidget(self.main_memory)
        self.gridlayout1.addWidget(self.stacks,0,0,1,1)
        self.tabs.addTab(self.books_tab,QtGui.QIcon(":/library"),"")

        self.jobs_tab = QtGui.QWidget()
        self.jobs_tab.setObjectName("jobs_tab")

        self.gridlayout4 = QtGui.QGridLayout(self.jobs_tab)
        self.gridlayout4.setObjectName("gridlayout4")
        self.tabs.addTab(self.jobs_tab,"")
        self.gridlayout.addWidget(self.tabs,2,0,1,1)

        self.hboxlayout2 = QtGui.QHBoxLayout()
        self.hboxlayout2.setSpacing(6)




        self.hboxlayout2.setObjectName("hboxlayout2")

        self.book_cover = CoverDisplay(self.centralwidget)
        self.book_cover.setMaximumSize(QtCore.QSize(60,80))
        self.book_cover.setAcceptDrops(True)
        self.book_cover.setScaledContents(True)
        self.book_cover.setObjectName("book_cover")
        self.hboxlayout2.addWidget(self.book_cover)

        self.book_info = QtGui.QLabel(self.centralwidget)
        self.book_info.setTextFormat(QtCore.Qt.RichText)
        self.book_info.setObjectName("book_info")
        self.hboxlayout2.addWidget(self.book_info)
        self.gridlayout.addLayout(self.hboxlayout2,3,0,1,1)
        MainWindow.setCentralWidget(self.centralwidget)

        self.tool_bar = QtGui.QToolBar(MainWindow)
        self.tool_bar.setMinimumSize(QtCore.QSize(0,0))
        self.tool_bar.setMovable(False)
        self.tool_bar.setOrientation(QtCore.Qt.Horizontal)
        self.tool_bar.setIconSize(QtCore.QSize(64,64))
        self.tool_bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        self.tool_bar.setObjectName("tool_bar")
        MainWindow.addToolBar(self.tool_bar)

        self.action_add = QtGui.QAction(MainWindow)
        self.action_add.setIcon(QtGui.QIcon(":/images/addfile.png"))
        self.action_add.setAutoRepeat(False)
        self.action_add.setObjectName("action_add")

        self.action_del = QtGui.QAction(MainWindow)
        self.action_del.setIcon(QtGui.QIcon(":/images/delfile.png"))
        self.action_del.setObjectName("action_del")

        self.action_edit = QtGui.QAction(MainWindow)
        self.action_edit.setIcon(QtGui.QIcon(":/images/edit.png"))
        self.action_edit.setAutoRepeat(False)
        self.action_edit.setObjectName("action_edit")
        self.tool_bar.addAction(self.action_add)
        self.tool_bar.addAction(self.action_del)
        self.tool_bar.addAction(self.action_edit)
        self.label.setBuddy(self.search)

        self.retranslateUi(MainWindow)
        self.tabs.setCurrentIndex(0)
        self.stacks.setCurrentIndex(0)
        QtCore.QObject.connect(self.clear_button,QtCore.SIGNAL("clicked()"),self.search.clear)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QtGui.QApplication.translate("MainWindow", "libprs500", None, QtGui.QApplication.UnicodeUTF8))
        self.df.setText(QtGui.QApplication.translate("MainWindow", "For help visit <a href=\"https://libprs500.kovidgoyal.net/wiki/GuiUsage\">http://libprs500.kovidgoyal.net</a><br><br><b>libprs500</b>: %1 by <b>Kovid Goyal</b> &copy; 2006<br>%2 %3 %4", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("MainWindow", "&Search:", None, QtGui.QApplication.UnicodeUTF8))
        self.search.setToolTip(QtGui.QApplication.translate("MainWindow", "Search the list of books by title or author<br><br>Words separated by spaces are ANDed", None, QtGui.QApplication.UnicodeUTF8))
        self.search.setWhatsThis(QtGui.QApplication.translate("MainWindow", "Search the list of books by title, author, publisher, tags and comments<br><br>Words separated by spaces are ANDed", None, QtGui.QApplication.UnicodeUTF8))
        self.clear_button.setToolTip(QtGui.QApplication.translate("MainWindow", "Reset Quick Search", None, QtGui.QApplication.UnicodeUTF8))
        self.clear_button.setText(QtGui.QApplication.translate("MainWindow", "...", None, QtGui.QApplication.UnicodeUTF8))
        self.tabs.setTabText(self.tabs.indexOf(self.books_tab), QtGui.QApplication.translate("MainWindow", "Books", None, QtGui.QApplication.UnicodeUTF8))
        self.tabs.setTabText(self.tabs.indexOf(self.jobs_tab), QtGui.QApplication.translate("MainWindow", "Jobs", None, QtGui.QApplication.UnicodeUTF8))
        self.tabs.setTabToolTip(self.tabs.indexOf(self.jobs_tab),QtGui.QApplication.translate("MainWindow", "Show jobs being currently processed", None, QtGui.QApplication.UnicodeUTF8))
        self.book_info.setText(QtGui.QApplication.translate("MainWindow", "<table><tr><td><b>Title: </b>%1</td><td><b>&nbsp;Size:</b> %2</td></tr><tr><td><b>Author: </b>%3</td><td><b>&nbsp;Type: </b>%4</td></tr></table>", None, QtGui.QApplication.UnicodeUTF8))
        self.action_add.setText(QtGui.QApplication.translate("MainWindow", "Add books to Library", None, QtGui.QApplication.UnicodeUTF8))
        self.action_add.setShortcut(QtGui.QApplication.translate("MainWindow", "A", None, QtGui.QApplication.UnicodeUTF8))
        self.action_del.setText(QtGui.QApplication.translate("MainWindow", "Delete books", None, QtGui.QApplication.UnicodeUTF8))
        self.action_del.setShortcut(QtGui.QApplication.translate("MainWindow", "Del", None, QtGui.QApplication.UnicodeUTF8))
        self.action_edit.setText(QtGui.QApplication.translate("MainWindow", "Edit meta-information", None, QtGui.QApplication.UnicodeUTF8))
        self.action_edit.setShortcut(QtGui.QApplication.translate("MainWindow", "E", None, QtGui.QApplication.UnicodeUTF8))

from widgets import DeviceView, CoverDisplay
from progress import AnimatedTabWidget
from library import BooksView, SearchBox
import images_rc
