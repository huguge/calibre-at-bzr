#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, traceback, re
from Queue import Empty, Queue
from contextlib import closing


from PyQt4.Qt import QWizard, QWizardPage, QPixmap, Qt, QAbstractListModel, \
    QVariant, QItemSelectionModel, SIGNAL, QObject, QTimer
from calibre import __appname__, patheq
from calibre.library.database2 import LibraryDatabase2
from calibre.library.move import MoveLibrary
from calibre.resources import server_resources
from calibre.gui2.wizard.send_email import smtp_prefs
from calibre.gui2.wizard.device_ui import Ui_WizardPage as DeviceUI
from calibre.gui2.wizard.library_ui import Ui_WizardPage as LibraryUI
from calibre.gui2.wizard.finish_ui import Ui_WizardPage as FinishUI
from calibre.gui2.wizard.kindle_ui import Ui_WizardPage as KindleUI
from calibre.gui2.wizard.stanza_ui import Ui_WizardPage as StanzaUI
from calibre.gui2 import min_available_height, available_width

from calibre.utils.config import dynamic, prefs
from calibre.gui2 import NONE, choose_dir, error_dialog
from calibre.gui2.dialogs.progress import ProgressDialog

class Device(object):

    output_profile = 'default'
    output_format = 'EPUB'
    name = _('Default')
    manufacturer = _('Default')
    id = 'default'

    @classmethod
    def set_output_profile(cls):
        if cls.output_profile:
            from calibre.ebooks.conversion.config import load_defaults, save_defaults
            recs = load_defaults('page_setup')
            recs['output_profile'] = cls.output_profile
            save_defaults('page_setup', recs)

    @classmethod
    def set_output_format(cls):
        if cls.output_format:
            prefs.set('output_format', cls.output_format)

    @classmethod
    def commit(cls):
        cls.set_output_profile()
        cls.set_output_format()

class Kindle(Device):

    output_profile = 'kindle'
    output_format  = 'MOBI'
    name = 'Kindle 1 or 2'
    manufacturer = 'Amazon'
    id = 'kindle'

class KindleDX(Kindle):

    output_profile = 'kindle_dx'
    output_format  = 'MOBI'
    name = 'Kindle DX'
    id = 'kindledx'

class Sony500(Device):

    output_profile = 'sony'
    name = 'SONY PRS 500'
    output_format = 'LRF'
    manufacturer = 'SONY'
    id = 'prs500'

class Sony505(Sony500):

    output_format = 'EPUB'
    name = 'SONY PRS 505/700'
    id = 'prs505'

class CybookG3(Device):

    name = 'Cybook Gen 3'
    output_format = 'MOBI'
    output_profile = 'cybookg3'
    manufacturer = 'Booken'
    id = 'cybookg3'

class CybookOpus(CybookG3):

    name = 'Cybook Opus'
    output_format = 'EPUB'
    id = 'cybook_opus'

class BeBook(Device):

    name = 'BeBook or BeBook Mini'
    output_format = 'EPUB'
    output_profile = 'sony'
    manufacturer = 'Endless Ideas'
    id = 'bebook'

class iPhone(Device):

    name = 'iPhone/iTouch + Stanza'
    output_format = 'EPUB'
    manufacturer = 'Apple'
    id = 'iphone'

class Hanlin(Device):

    name = 'Hanlin V3'
    output_format = 'MOBI'
    output_profile = 'hanlinv3'
    manufacturer = 'Hanlin'
    id = 'hanlinv3'

def get_devices():
    for x in globals().values():
        if isinstance(x, type) and issubclass(x, Device):
            yield x

def get_manufacturers():
    mans = set([])
    for x in get_devices():
        mans.add(x.manufacturer)
    mans.remove(_('Default'))
    return [_('Default')] + sorted(mans)

def get_devices_of(manufacturer):
    ans = [d for d in get_devices() if d.manufacturer == manufacturer]
    return sorted(ans, cmp=lambda x,y:cmp(x.name, y.name))

class ManufacturerModel(QAbstractListModel):

    def __init__(self):
        QAbstractListModel.__init__(self)
        self.manufacturers = get_manufacturers()

    def rowCount(self, p):
        return len(self.manufacturers)

    def columnCount(self, p):
        return 1

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return QVariant(self.manufacturers[index.row()])
        if role == Qt.UserRole:
            return self.manufacturers[index.row()]
        return NONE

    def index_of(self, man):
        for i, x in enumerate(self.manufacturers):
            if x == man:
                return self.index(i)

class DeviceModel(QAbstractListModel):

    def __init__(self, manufacturer):
        QAbstractListModel.__init__(self)
        self.devices = get_devices_of(manufacturer)

    def rowCount(self, p):
        return len(self.devices)

    def columnCount(self, p):
        return 1

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return QVariant(self.devices[index.row()].name)
        if role == Qt.UserRole:
            return self.devices[index.row()]
        return NONE

    def index_of(self, dev):
        for i, device in enumerate(self.devices):
            if device is dev:
                return self.index(i)

class KindlePage(QWizardPage, KindleUI):

    ID = 3

    def __init__(self):
        QWizardPage.__init__(self)
        self.setupUi(self)

    def initializePage(self):
        opts = smtp_prefs().parse()
        for x in opts.accounts.keys():
            if x.strip().endswith('@kindle.com'):
                self.to_address.setText(x)
        def x():
            t = unicode(self.to_address.text())
            if t.strip():
                return t.strip()

        self.send_email_widget.initialize(x)

    def commit(self):
        x = unicode(self.to_address.text()).strip()
        parts = x.split('@')
        if len(parts) < 2 or not parts[0]: return

        if self.send_email_widget.set_email_settings(True):
            conf = smtp_prefs()
            accounts = conf.get('accounts', {})
            if not accounts: accounts = {}
            for y in accounts.values():
                y[2] = False
            accounts[x] = ['AZW, MOBI, TPZ, PRC, AZW1', True, True]
            conf.set('accounts', accounts)

    def nextId(self):
        return FinishPage.ID

class StanzaPage(QWizardPage, StanzaUI):

    ID = 5

    def __init__(self):
        QWizardPage.__init__(self)
        self.setupUi(self)
        self.connect(self.content_server, SIGNAL('stateChanged(int)'), self.set_port)

    def initializePage(self):
        from calibre.gui2 import config
        yes = config['autolaunch_server']
        self.content_server.setChecked(yes)
        self.set_port()

    def nextId(self):
        return FinishPage.ID

    def commit(self):
        p = self.set_port()
        if p is not None:
            from calibre.library import server_config
            c = server_config()
            c.set('port', p)


    def set_port(self, *args):
        if not self.content_server.isChecked(): return
        import socket
        s = socket.socket()
        with closing(s):
            for p in range(8080, 8100):
                try:
                    s.bind(('0.0.0.0', p))
                    t = unicode(self.instructions.text())
                    t = re.sub(r':\d+', ':'+str(p), t)
                    self.instructions.setText(t)
                    return p
                except:
                    continue




class DevicePage(QWizardPage, DeviceUI):

    ID = 2

    def __init__(self):
        QWizardPage.__init__(self)
        self.setupUi(self)
        self.registerField("manufacturer", self.manufacturer_view)
        self.registerField("device", self.device_view)

    def initializePage(self):
        self.man_model = ManufacturerModel()
        self.manufacturer_view.setModel(self.man_model)
        previous = dynamic.get('welcome_wizard_device', False)
        if previous:
            previous = [x for x in get_devices() if \
                    x.id == previous]
            if not previous:
                previous = [Device]
            previous = previous[0]
        else:
            previous = Device
        idx = self.man_model.index_of(previous.manufacturer)
        if idx is None:
            idx = self.man_model.index_of(Device.manufacturer)
            previous = Device
        self.manufacturer_view.selectionModel().select(idx,
                QItemSelectionModel.Select)
        self.dev_model = DeviceModel(self.man_model.data(idx, Qt.UserRole))
        idx = self.dev_model.index_of(previous)
        self.device_view.setModel(self.dev_model)
        self.device_view.selectionModel().select(idx,
                QItemSelectionModel.Select)
        self.connect(self.manufacturer_view.selectionModel(),
                SIGNAL('selectionChanged(QItemSelection,QItemSelection)'),
                self.manufacturer_changed)

    def manufacturer_changed(self, current, previous):
        new = list(current.indexes())[0]
        man = self.man_model.data(new, Qt.UserRole)
        self.dev_model = DeviceModel(man)
        self.device_view.setModel(self.dev_model)
        self.device_view.selectionModel().select(self.dev_model.index(0),
                QItemSelectionModel.Select)

    def commit(self):
        idx = list(self.device_view.selectionModel().selectedIndexes())[0]
        dev = self.dev_model.data(idx, Qt.UserRole)
        dev.commit()
        dynamic.set('welcome_wizard_device', dev.id)

    def nextId(self):
        idx = list(self.device_view.selectionModel().selectedIndexes())[0]
        dev = self.dev_model.data(idx, Qt.UserRole)
        if dev in (Kindle, KindleDX):
            return KindlePage.ID
        if dev is iPhone:
            return StanzaPage.ID
        return FinishPage.ID

class MoveMonitor(QObject):

    def __init__(self, worker, rq, callback, parent):
        QObject.__init__(self, parent)
        self.worker = worker
        self.rq = rq
        self.callback = callback
        self.parent = parent

        self.worker.start()
        self.dialog = ProgressDialog(_('Moving library...'), '',
                max=self.worker.total, parent=parent)
        self.dialog.button_box.setDisabled(True)
        self.dialog.setModal(True)
        self.dialog.show()
        self.timer = QTimer(self)
        self.connect(self.timer, SIGNAL('timeout()'), self.check)
        self.timer.start(200)

    def check(self):
        if self.worker.is_alive():
            self.update()
        else:
            self.timer.stop()
            self.dialog.hide()
            if self.worker.failed:
                error_dialog(self.parent, _('Failed to move library'),
                    _('Failed to move library'), self.worker.details, show=True)
                return self.callback(None)
            else:
                return self.callback(self.worker.to)

    def update(self):
        try:
            title = self.rq.get_nowait()[-1]
            self.dialog.value += 1
            self.dialog.set_msg(_('Copied') + ' '+title)
        except Empty:
            pass


class Callback(object):

    def __init__(self, callback):
        self.callback = callback

    def __call__(self, newloc):
        if newloc is not None:
            prefs['library_path'] = newloc
        self.callback(newloc)

_mm = None
def move_library(oldloc, newloc, parent, callback_on_complete):
    callback = Callback(callback_on_complete)
    try:
        if not os.path.exists(os.path.join(newloc, 'metadata.db')):
            if oldloc and os.access(os.path.join(oldloc, 'metadata.db'), os.R_OK):
                # Move old library to new location
                try:
                    db = LibraryDatabase2(oldloc)
                except:
                    return move_library(None, newloc, parent,
                        callback)
                else:
                    rq = Queue()
                    m = MoveLibrary(oldloc, newloc, db.data.count(), rq)
                    global _mm
                    _mm = MoveMonitor(m, rq, callback, parent)
                    return
            else:
                # Create new library at new location
                db = LibraryDatabase2(newloc)
                callback(newloc)
                return

        # Try to load existing library at new location
        try:
            ndb = LibraryDatabase2(newloc)
        except Exception, err:
            det = traceback.format_exc()
            error_dialog(parent, _('Invalid database'),
                _('<p>An invalid library already exists at '
                    '%s, delete it before trying to move the '
                    'existing library.<br>Error: %s')%(newloc,
                        str(err)), det, show=True)
            callback(None)
            return
        else:
            callback(newloc)
            return
    except Exception, err:
        det = traceback.format_exc()
        error_dialog(parent, _('Could not move library'),
                unicode(err), det, show=True)
    callback(None)

class LibraryPage(QWizardPage, LibraryUI):

    ID = 1

    def __init__(self):
        QWizardPage.__init__(self)
        self.setupUi(self)
        self.registerField('library_location', self.location)
        self.connect(self.button_change, SIGNAL('clicked()'), self.change)

    def change(self):
        dir = choose_dir(self, 'database location dialog',
                         _('Select location for books'))
        if dir:
            self.location.setText(dir)

    def initializePage(self):
        lp = prefs['library_path']
        if not lp:
            lp = os.path.expanduser('~')
        self.location.setText(lp)

    def isComplete(self):
        lp = unicode(self.location.text())
        return lp and os.path.exists(lp) and os.path.isdir(lp) and os.access(lp,
                os.W_OK)

    def commit(self, completed):
        oldloc = prefs['library_path']
        newloc = unicode(self.location.text())
        if not patheq(oldloc, newloc):
            move_library(oldloc, newloc, self.wizard(), completed)
            return True
        return False

    def nextId(self):
        return DevicePage.ID

class FinishPage(QWizardPage, FinishUI):

    ID = 4

    def __init__(self):
        QWizardPage.__init__(self)
        self.setupUi(self)

    def nextId(self):
        return -1



class Wizard(QWizard):

    def __init__(self, parent):
        QWizard.__init__(self, parent)
        self.setWindowTitle(__appname__+' '+_('welcome wizard'))
        p  = QPixmap()
        p.loadFromData(server_resources['calibre.png'])
        self.setPixmap(self.LogoPixmap, p.scaledToHeight(80,
            Qt.SmoothTransformation))
        self.setPixmap(self.WatermarkPixmap,
            QPixmap(':/images/welcome_wizard.svg'))
        self.setPixmap(self.BackgroundPixmap, QPixmap(':/images/wizard.svg'))
        self.device_page = DevicePage()
        self.library_page = LibraryPage()
        self.finish_page = FinishPage()
        bt = unicode(self.buttonText(self.FinishButton))
        t = unicode(self.finish_page.finish_text.text())
        self.finish_page.finish_text.setText(t%bt)
        self.kindle_page = KindlePage()
        self.stanza_page = StanzaPage()
        self.setPage(self.library_page.ID, self.library_page)
        self.setPage(self.device_page.ID, self.device_page)
        self.setPage(self.finish_page.ID, self.finish_page)
        self.setPage(self.kindle_page.ID, self.kindle_page)
        self.setPage(self.stanza_page.ID, self.stanza_page)

        self.device_extra_page = None
        nh, nw = min_available_height()-75, available_width()-30
        if nh < 0:
            nh = 580
        if nw < 0:
            nw = 400
        nh = min(400, nh)
        nw = min(580, nw)
        self.resize(nw, nh)


    def accept(self):
        self.device_page.commit()
        if not self.library_page.commit(self.completed):
            self.completed(None)

    def completed(self, newloc):
        return QWizard.accept(self)

def wizard(parent=None):
    w = Wizard(parent)
    return w

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app = QApplication([])
    wizard().exec_()

