# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget, QListWidgetItem, Qt, QVariant, SIGNAL

from calibre.gui2.device_drivers.configwidget_ui import Ui_ConfigWidget

class ConfigWidget(QWidget, Ui_ConfigWidget):

    def __init__(self, settings, all_formats, supports_subdirs,
        must_read_metadata):

        QWidget.__init__(self)
        Ui_ConfigWidget.__init__(self)
        self.setupUi(self)
        
        self.settings = settings
        
        format_map = settings.format_map
        disabled_formats = list(set(all_formats).difference(format_map))
        for format in format_map + disabled_formats:
            item = QListWidgetItem(format, self.columns)
            item.setData(Qt.UserRole, QVariant(format))
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked if format in format_map else Qt.Unchecked)

        self.connect(self.column_up, SIGNAL('clicked()'), self.up_column)
        self.connect(self.column_down, SIGNAL('clicked()'), self.down_column)

        if supports_subdirs:
            self.opt_use_subdirs.setChecked(self.settings.use_subdirs)
        else:
            self.opt_use_subdirs.hide()
        if not must_read_metadata:
            self.opt_read_metadata.setChecked(self.settings.read_metadata)
        else:
            self.opt_read_metadata.hide()

    def up_column(self):
        idx = self.columns.currentRow()
        if idx > 0:
            self.columns.insertItem(idx-1, self.columns.takeItem(idx))
            self.columns.setCurrentRow(idx-1)

    def down_column(self):
        idx = self.columns.currentRow()
        if idx < self.columns.count()-1:
            self.columns.insertItem(idx+1, self.columns.takeItem(idx))
            self.columns.setCurrentRow(idx+1)

    def format_map(self):
        formats = [unicode(self.columns.item(i).data(Qt.UserRole).toString()) for i in range(self.columns.count()) if self.columns.item(i).checkState()==Qt.Checked]
        return formats

    def use_subdirs(self):
        return self.opt_use_subdirs.isChecked()

    def read_metadata(self):
        return self.opt_read_metadata.isChecked()
