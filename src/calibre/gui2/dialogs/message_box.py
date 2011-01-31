#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import QDialog, QIcon, QApplication, QSize, QKeySequence, \
    QAction, Qt

from calibre.constants import __version__
from calibre.gui2.dialogs.message_box_ui import Ui_Dialog

class MessageBox(QDialog, Ui_Dialog):

    ERROR = 0
    WARNING = 1
    INFO = 2
    QUESTION = 3

    def __init__(self, type_, title, msg, det_msg='', show_copy_button=True,
            parent=None):
        QDialog.__init__(self, parent)
        icon = {
                self.ERROR : 'error',
                self.WARNING: 'warning',
                self.INFO:    'information',
                self.QUESTION: 'question',
        }[type_]
        icon = 'dialog_%s.png'%icon
        self.icon = QIcon(I(icon))
        self.setupUi(self)

        self.setWindowTitle(title)
        self.setWindowIcon(self.icon)
        self.icon_label.setPixmap(self.icon.pixmap(128, 128))
        self.msg.setText(msg)
        self.det_msg.setPlainText(det_msg)
        self.det_msg.setVisible(False)

        if show_copy_button:
            self.ctc_button = self.bb.addButton(_('&Copy to clipboard'),
                    self.bb.ActionRole)
            self.ctc_button.clicked.connect(self.copy_to_clipboard)


        self.show_det_msg = _('Show &details')
        self.hide_det_msg = _('Hide &details')
        self.det_msg_toggle = self.bb.addButton(self.show_det_msg, self.bb.ActionRole)
        self.det_msg_toggle.clicked.connect(self.toggle_det_msg)
        self.det_msg_toggle.setToolTip(
                _('Show detailed information about this error'))

        self.copy_action = QAction(self)
        self.addAction(self.copy_action)
        self.copy_action.setShortcuts(QKeySequence.Copy)
        self.copy_action.triggered.connect(self.copy_to_clipboard)

        self.is_question = type_ == self.QUESTION
        if self.is_question:
            self.bb.setStandardButtons(self.bb.Yes|self.bb.No)
            self.bb.button(self.bb.Yes).setDefault(True)
        else:
            self.bb.button(self.bb.Ok).setDefault(True)

        if not det_msg:
            self.det_msg_toggle.setVisible(False)

        self.do_resize()


    def toggle_det_msg(self, *args):
        vis = unicode(self.det_msg_toggle.text()) == self.hide_det_msg
        self.det_msg_toggle.setText(self.show_det_msg if vis else
                self.hide_det_msg)
        self.det_msg.setVisible(not vis)
        self.do_resize()

    def do_resize(self):
        sz = self.sizeHint() + QSize(100, 0)
        sz.setWidth(min(500, sz.width()))
        sz.setHeight(min(500, sz.height()))
        self.resize(sz)

    def copy_to_clipboard(self, *args):
        QApplication.clipboard().setText(
                'calibre, version %s\n%s: %s\n\n%s' %
                (__version__, unicode(self.windowTitle()),
                    unicode(self.msg.text()),
                    unicode(self.det_msg.toPlainText())))
        self.ctc_button.setText(_('Copied'))

    def showEvent(self, ev):
        ret = QDialog.showEvent(self, ev)
        if self.is_question:
            try:
                self.bb.button(self.bb.Yes).setFocus(Qt.OtherFocusReason)
            except:
                pass# Buttons were changed
        else:
            self.bb.button(self.bb.Ok).setFocus(Qt.OtherFocusReason)
        return ret

    def set_details(self, msg):
        if not msg:
            msg = ''
        self.det_msg.setPlainText(msg)
        self.det_msg_toggle.setText(self.show_det_msg)
        self.det_msg_toggle.setVisible(bool(msg))
        self.det_msg.setVisible(False)
        self.do_resize()

if __name__ == '__main__':
    app = QApplication([])
    from calibre.gui2 import question_dialog
    print question_dialog(None, 'title', 'msg <a href="http://google.com">goog</a> ',
            det_msg='det '*1000,
            show_copy_button=True)
