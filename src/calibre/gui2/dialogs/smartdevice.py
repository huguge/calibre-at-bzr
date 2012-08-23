#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import (QDialog, QLineEdit, Qt)

from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.smartdevice_ui import Ui_Dialog

class SmartdeviceDialog(QDialog, Ui_Dialog):

    def __init__(self, parent):
        QDialog.__init__(self, parent)
        Ui_Dialog.__init__(self)
        self.setupUi(self)

        self.password_box.setToolTip('<p>' +
             _('Use a password if calibre is running on a network that '
              'is not secure. For example, if you run calibre on a laptop, '
              'use that laptop in an airport, and want to connect your '
              'smart device to calibre, you should use a password.') + '</p>')

        self.autostart_box.setToolTip('<p>' +
            _('Check this box if you want calibre to automatically start the '
              'smart device interface when calibre starts. You should not do '
              'this if you are using a network that is not secure and you '
              'are not setting a password.') + '</p>')

        self.use_fixed_port.setToolTip('<p>' +
            _('Check this box if you want calibre to use a fixed network '
              'port. Normally you will not need to do this. However, if '
              'your device consistently fails to connect to calibre, '
              'try checking this box.') + '</p>')

        self.fixed_port.setToolTip('<p>' +
            _('A port number must be a 4-digit integer less than 32,000. No '
              'two network applications on the same computer can use '
              'the same port number. If calibre says that it fails to connect '
              'to the port, try a different number.') + '</p>')

        self.show_password.stateChanged[int].connect(self.toggle_password)
        self.use_fixed_port.stateChanged[int].connect(self.use_fixed_port_changed)

        self.device_manager = parent.device_manager

        if self.device_manager.get_option('smartdevice', 'autostart'):
            self.autostart_box.setChecked(True)

        pw = self.device_manager.get_option('smartdevice', 'password')
        if pw:
            self.password_box.setText(pw)

        use_fixed_port = self.device_manager.get_option('smartdevice', 'use_fixed_port')
        port_number = self.device_manager.get_option('smartdevice', 'port_number')
        self.fixed_port.setText(port_number)
        self.use_fixed_port.setChecked(use_fixed_port);
        if not use_fixed_port:
            self.fixed_port.setEnabled(False);

        if pw:
            self.password_box.setText(pw)

        self.resize(self.sizeHint())

    def use_fixed_port_changed(self, state):
        self.fixed_port.setEnabled(state == Qt.Checked)

    def toggle_password(self, state):
        self.password_box.setEchoMode(QLineEdit.Password if state ==
                Qt.Unchecked else QLineEdit.Normal)

    def accept(self):
        self.device_manager.set_option('smartdevice', 'password',
                                       unicode(self.password_box.text()))
        self.device_manager.set_option('smartdevice', 'autostart',
                                       self.autostart_box.isChecked())
        self.device_manager.set_option('smartdevice', 'use_fixed_port',
                                       self.use_fixed_port.isChecked())
        self.device_manager.set_option('smartdevice', 'port_number',
                                       unicode(self.fixed_port.text()))

        message = self.device_manager.start_plugin('smartdevice')

        if not self.device_manager.is_running('smartdevice'):
            error_dialog(self, _('Problem starting smartdevice'),
                _('The snart device driver did not start. It said "%s"')%message, show=True)
        else:
            QDialog.accept(self)

