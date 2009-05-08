#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QDialog, QWidget, SIGNAL, Qt, QDialogButtonBox, QVBoxLayout

from calibre.gui2.convert.xpath_wizard_ui import Ui_Form
from calibre.gui2.convert.xpath_edit_ui import Ui_Form as Ui_Edit


class WizardWidget(QWidget, Ui_Form):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

    @property
    def xpath(self):
        tag = unicode(self.tag.currentText()).strip()
        if tag != '*':
            tag = 'h:'+tag
        attr, val = map(unicode, (self.attribute.text(), self.value.text()))
        attr, val = attr.strip(), val.strip()
        q = ''
        if attr:
            if val:
                q = '[re:test(@%s, "%s", "i")]'%(attr, val)
            else:
                q = '[@%s]'%attr
        expr = '//'+tag + q
        return expr

class Wizard(QDialog):

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.resize(400, 300)
        self.verticalLayout = QVBoxLayout(self)
        self.widget = WizardWidget(self)
        self.verticalLayout.addWidget(self.widget)
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)
        self.verticalLayout.addWidget(self.buttonBox)

        self.connect(self.buttonBox, SIGNAL("accepted()"), self.accept)
        self.connect(self.buttonBox, SIGNAL("rejected()"), self.reject)
        self.setModal(Qt.WindowModal)

    @property
    def xpath(self):
        return self.widget.xpath


class XPathEdit(QWidget, Ui_Edit):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self.connect(self.button, SIGNAL('clicked()'), self.wizard)

    def wizard(self):
        wiz = Wizard(self)
        if wiz.exec_() == wiz.Accepted:
            self.edit.setText(wiz.xpath)


    def set_msg(self, msg):
        self.msg.setText(msg)

    @property
    def text(self):
        return unicode(self.edit.text())

    @property
    def xpath(self):
        return self.text

    def check(self):
        from calibre.ebooks.oeb.base import XPNSMAP
        from lxml.etree import XPath
        try:
            if self.text.strip():
                XPath(self.text, namespaces=XPNSMAP)
        except:
            import traceback
            traceback.print_exc()
            return False
        return True



