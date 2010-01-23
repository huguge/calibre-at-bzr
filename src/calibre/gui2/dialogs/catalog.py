#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys

from PyQt4.Qt import QDialog

from calibre.customize.ui import config
from calibre.gui2.dialogs.catalog_ui import Ui_Dialog
from calibre.gui2 import dynamic
from calibre.customize.ui import catalog_plugins

class Catalog(QDialog, Ui_Dialog):
    ''' Catalog Dialog builder'''

    def __init__(self, parent, dbspec, ids):
        import re, cStringIO
        from calibre import prints as info
        from PyQt4.uic import compileUi

        QDialog.__init__(self, parent)

        # Run the dialog setup generated from catalog.ui
        self.setupUi(self)
        self.dbspec, self.ids = dbspec, ids

        # Display the number of books we've been passed
        self.count.setText(unicode(self.count.text()).format(len(ids)))

        # Display the last-used title
        self.title.setText(dynamic.get('catalog_last_used_title',
            _('My Books')))

        self.fmts, self.widgets = [], []

        from calibre.customize.builtins import plugins as builtin_plugins

        for plugin in catalog_plugins():
            if plugin.name in config['disabled_plugins']:
                continue

            name = plugin.name.lower().replace(' ', '_')
            if type(plugin) in builtin_plugins:
                try:
                    catalog_widget = __import__('calibre.gui2.catalog.'+name,
                            fromlist=[1])
                    pw = catalog_widget.PluginWidget()
                    pw.initialize(name)
                    pw.ICON = I('forward.svg')
                    self.widgets.append(pw)
                    [self.fmts.append([file_type.upper(), pw.sync_enabled,pw]) for file_type in plugin.file_types]
                except ImportError:
                    info("ImportError initializing %s" % name)
                    continue
            else:
                # Load dynamic tab
                form = os.path.join(plugin.resources_path,'%s.ui' % name)
                klass = os.path.join(plugin.resources_path,'%s.py' % name)
                compiled_form = os.path.join(plugin.resources_path,'%s_ui.py' % name)

                if os.path.exists(form) and os.path.exists(klass):
                    #info("Adding widget for user-installed Catalog plugin %s" % plugin.name)

                    # Compile the .ui form provided in plugin.zip
                    if not os.path.exists(compiled_form):
                        # info('\tCompiling form', form)
                        buf = cStringIO.StringIO()
                        compileUi(form, buf)
                        dat = buf.getvalue()
                        dat = re.compile(r'QtGui.QApplication.translate\(.+?,\s+"(.+?)(?<!\\)",.+?\)',
                                         re.DOTALL).sub(r'_("\1")', dat)
                        open(compiled_form, 'wb').write(dat)

                    # Import the dynamic PluginWidget() from .py file provided in plugin.zip
                    try:
                        sys.path.insert(0, plugin.resources_path)
                        catalog_widget = __import__(name, fromlist=[1])
                        pw = catalog_widget.PluginWidget()
                        pw.initialize(name)
                        pw.ICON = I('forward.svg')
                        self.widgets.append(pw)
                        [self.fmts.append([file_type.upper(), pw.sync_enabled,pw]) for file_type in plugin.file_types]
                    except ImportError:
                        info("ImportError with %s" % name)
                        continue
                    finally:
                        sys.path.remove(plugin.resources_path)

                else:
                    info("No dynamic tab resources found for %s" % name)

        self.widgets = sorted(self.widgets, cmp=lambda x,y:cmp(x.TITLE, y.TITLE))

        # Generate a sorted list of installed catalog formats/sync_enabled pairs
        fmts = sorted([x[0] for x in self.fmts])

        self.sync_enabled_formats = []
        for fmt in self.fmts:
            if fmt[1]:
                self.sync_enabled_formats.append(fmt[0])

        # Callback when format changes
        self.format.currentIndexChanged.connect(self.format_changed)

        # Add the installed catalog format list to the format QComboBox
        self.format.addItems(fmts)

        pref = dynamic.get('catalog_preferred_format', 'CSV')
        idx = self.format.findText(pref)
        if idx > -1:
            self.format.setCurrentIndex(idx)

        if self.sync.isEnabled():
            self.sync.setChecked(dynamic.get('catalog_sync_to_device', True))

        self.format.currentIndexChanged.connect(self.show_plugin_tab)
        self.show_plugin_tab(None)


    def show_plugin_tab(self, idx):
        cf = unicode(self.format.currentText()).lower()
        while self.tabs.count() > 1:
            self.tabs.removeTab(1)
        for pw in self.widgets:
            if cf in pw.formats:
                self.tabs.addTab(pw, pw.TITLE)
                break

    def format_changed(self, idx):
        cf = unicode(self.format.currentText())
        if cf in self.sync_enabled_formats:
            self.sync.setEnabled(True)
        else:
            self.sync.setDisabled(True)
            self.sync.setChecked(False)

    @property
    def fmt_options(self):
        ans = {}
        if self.tabs.count() > 1:
            w = self.tabs.widget(1)
            ans = w.options()
        return ans

    def accept(self):
        self.catalog_format = unicode(self.format.currentText())
        dynamic.set('catalog_preferred_format', self.catalog_format)
        self.catalog_title = unicode(self.title.text())
        dynamic.set('catalog_last_used_title', self.catalog_title)
        self.catalog_sync = bool(self.sync.isChecked())
        dynamic.set('catalog_sync_to_device', self.catalog_sync)
        QDialog.accept(self)
