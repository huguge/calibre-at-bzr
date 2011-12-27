#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

# Imports {{{
import os, math, re, glob, sys
from base64 import b64encode
from functools import partial

from PyQt4.Qt import (QSize, QSizePolicy, QUrl, SIGNAL, Qt, QTimer,
                     QPainter, QPalette, QBrush, QFontDatabase, QDialog,
                     QColor, QPoint, QImage, QRegion, QVariant, QIcon,
                     QFont, pyqtSignature, QAction, QByteArray, QMenu,
                     pyqtSignal)
from PyQt4.QtWebKit import QWebPage, QWebView, QWebSettings

from calibre.utils.config import Config, StringConfig
from calibre.utils.localization import get_language
from calibre.gui2.viewer.config_ui import Ui_Dialog
from calibre.gui2.viewer.flip import SlideFlip
from calibre.gui2.viewer.gestures import Gestures
from calibre.gui2.shortcuts import Shortcuts, ShortcutConfig
from calibre.constants import iswindows
from calibre import prints, guess_type
from calibre.gui2.viewer.keys import SHORTCUTS

# }}}

bookmarks = referencing = hyphenation = jquery = jquery_scrollTo = \
        hyphenator = images = hyphen_pats = None

def load_builtin_fonts():
    base = P('fonts/liberation/*.ttf')
    for f in glob.glob(base):
        QFontDatabase.addApplicationFont(f)
    return 'Liberation Serif', 'Liberation Sans', 'Liberation Mono'

# Config {{{
def config(defaults=None):
    desc = _('Options to customize the ebook viewer')
    if defaults is None:
        c = Config('viewer', desc)
    else:
        c = StringConfig(defaults, desc)

    c.add_opt('remember_window_size', default=False,
        help=_('Remember last used window size'))
    c.add_opt('user_css', default='',
              help=_('Set the user CSS stylesheet. This can be used to customize the look of all books.'))
    c.add_opt('max_view_width', default=6000,
            help=_('Maximum width of the viewer window, in pixels.'))
    c.add_opt('fit_images', default=True,
            help=_('Resize images larger than the viewer window to fit inside it'))
    c.add_opt('hyphenate', default=False, help=_('Hyphenate text'))
    c.add_opt('hyphenate_default_lang', default='en',
            help=_('Default language for hyphenation rules'))
    c.add_opt('remember_current_page', default=True,
            help=_('Save the current position in the document, when quitting'))
    c.add_opt('wheel_flips_pages', default=False,
            help=_('Have the mouse wheel turn pages'))
    c.add_opt('page_flip_duration', default=0.5,
            help=_('The time, in seconds, for the page flip animation. Default'
                ' is half a second.'))

    fonts = c.add_group('FONTS', _('Font options'))
    fonts('serif_family', default='Times New Roman' if iswindows else 'Liberation Serif',
          help=_('The serif font family'))
    fonts('sans_family', default='Verdana' if iswindows else 'Liberation Sans',
          help=_('The sans-serif font family'))
    fonts('mono_family', default='Courier New' if iswindows else 'Liberation Mono',
          help=_('The monospaced font family'))
    fonts('default_font_size', default=20, help=_('The standard font size in px'))
    fonts('mono_font_size', default=16, help=_('The monospaced font size in px'))
    fonts('standard_font', default='serif', help=_('The standard font type'))

    return c

class ConfigDialog(QDialog, Ui_Dialog):

    def __init__(self, shortcuts, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        opts = config().parse()
        self.opt_remember_window_size.setChecked(opts.remember_window_size)
        self.opt_remember_current_page.setChecked(opts.remember_current_page)
        self.opt_wheel_flips_pages.setChecked(opts.wheel_flips_pages)
        self.opt_page_flip_duration.setValue(opts.page_flip_duration)
        self.serif_family.setCurrentFont(QFont(opts.serif_family))
        self.sans_family.setCurrentFont(QFont(opts.sans_family))
        self.mono_family.setCurrentFont(QFont(opts.mono_family))
        self.default_font_size.setValue(opts.default_font_size)
        self.mono_font_size.setValue(opts.mono_font_size)
        self.standard_font.setCurrentIndex({'serif':0, 'sans':1, 'mono':2}[opts.standard_font])
        self.css.setPlainText(opts.user_css)
        self.css.setToolTip(_('Set the user CSS stylesheet. This can be used to customize the look of all books.'))
        self.max_view_width.setValue(opts.max_view_width)
        pats = [os.path.basename(x).split('.')[0].replace('-', '_') for x in
            glob.glob(P('viewer/hyphenate/patterns/*.js',
                allow_user_override=False))]
        names = list(map(get_language, pats))
        pmap = {}
        for i in range(len(pats)):
            pmap[names[i]] = pats[i]
        for x in sorted(names):
            self.hyphenate_default_lang.addItem(x, QVariant(pmap[x]))
        try:
            idx = pats.index(opts.hyphenate_default_lang)
        except ValueError:
            idx = pats.index('en_us')
        idx = self.hyphenate_default_lang.findText(names[idx])
        self.hyphenate_default_lang.setCurrentIndex(idx)
        self.hyphenate.setChecked(opts.hyphenate)
        self.hyphenate_default_lang.setEnabled(opts.hyphenate)
        self.shortcuts = shortcuts
        self.shortcut_config = ShortcutConfig(shortcuts, parent=self)
        p = self.tabs.widget(1)
        p.layout().addWidget(self.shortcut_config)
        self.opt_fit_images.setChecked(opts.fit_images)


    def accept(self, *args):
        if self.shortcut_config.is_editing:
            from calibre.gui2 import info_dialog
            info_dialog(self, _('Still editing'),
                    _('You are in the middle of editing a keyboard shortcut'
                        ' first complete that, by clicking outside the '
                        ' shortcut editing box.'), show=True)
            return
        c = config()
        c.set('serif_family', unicode(self.serif_family.currentFont().family()))
        c.set('sans_family', unicode(self.sans_family.currentFont().family()))
        c.set('mono_family', unicode(self.mono_family.currentFont().family()))
        c.set('default_font_size', self.default_font_size.value())
        c.set('mono_font_size', self.mono_font_size.value())
        c.set('standard_font', {0:'serif', 1:'sans', 2:'mono'}[self.standard_font.currentIndex()])
        c.set('user_css', unicode(self.css.toPlainText()))
        c.set('remember_window_size', self.opt_remember_window_size.isChecked())
        c.set('fit_images', self.opt_fit_images.isChecked())
        c.set('max_view_width', int(self.max_view_width.value()))
        c.set('hyphenate', self.hyphenate.isChecked())
        c.set('remember_current_page', self.opt_remember_current_page.isChecked())
        c.set('wheel_flips_pages', self.opt_wheel_flips_pages.isChecked())
        c.set('page_flip_duration', self.opt_page_flip_duration.value())
        idx = self.hyphenate_default_lang.currentIndex()
        c.set('hyphenate_default_lang',
                str(self.hyphenate_default_lang.itemData(idx).toString()))
        return QDialog.accept(self, *args)

# }}}

class Document(QWebPage): # {{{

    def set_font_settings(self):
        opts = config().parse()
        settings = self.settings()
        settings.setFontSize(QWebSettings.DefaultFontSize, opts.default_font_size)
        settings.setFontSize(QWebSettings.DefaultFixedFontSize, opts.mono_font_size)
        settings.setFontSize(QWebSettings.MinimumLogicalFontSize, 8)
        settings.setFontSize(QWebSettings.MinimumFontSize, 8)
        settings.setFontFamily(QWebSettings.StandardFont, {'serif':opts.serif_family, 'sans':opts.sans_family, 'mono':opts.mono_family}[opts.standard_font])
        settings.setFontFamily(QWebSettings.SerifFont, opts.serif_family)
        settings.setFontFamily(QWebSettings.SansSerifFont, opts.sans_family)
        settings.setFontFamily(QWebSettings.FixedFont, opts.mono_family)

    def do_config(self, parent=None):
        d = ConfigDialog(self.shortcuts, parent)
        if d.exec_() == QDialog.Accepted:
            self.set_font_settings()
            self.set_user_stylesheet()
            self.misc_config()
            self.after_load()

    def __init__(self, shortcuts, parent=None, resize_callback=lambda: None):
        QWebPage.__init__(self, parent)
        self.setObjectName("py_bridge")
        self.debug_javascript = False
        self.resize_callback = resize_callback
        self.current_language = None
        self.loaded_javascript = False

        self.setLinkDelegationPolicy(self.DelegateAllLinks)
        self.scroll_marks = []
        self.shortcuts = shortcuts
        pal = self.palette()
        pal.setBrush(QPalette.Background, QColor(0xee, 0xee, 0xee))
        self.setPalette(pal)

        settings = self.settings()

        # Fonts
        load_builtin_fonts()
        self.set_font_settings()

        # Security
        settings.setAttribute(QWebSettings.JavaEnabled, False)
        settings.setAttribute(QWebSettings.PluginsEnabled, False)
        settings.setAttribute(QWebSettings.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebSettings.JavascriptCanAccessClipboard, False)

        # Miscellaneous
        settings.setAttribute(QWebSettings.LinksIncludedInFocusChain, True)
        settings.setAttribute(QWebSettings.DeveloperExtrasEnabled, True)
        self.set_user_stylesheet()
        self.misc_config()

        # Load javascript
        self.mainFrame().javaScriptWindowObjectCleared.connect(
                self.add_window_objects)

    def set_user_stylesheet(self):
        raw = config().parse().user_css
        raw = '::selection {background:#ffff00; color:#000;}\nbody {background-color: white;}\n'+raw
        data = 'data:text/css;charset=utf-8;base64,'
        data += b64encode(raw.encode('utf-8'))
        self.settings().setUserStyleSheetUrl(QUrl(data))

    def misc_config(self):
        opts = config().parse()
        self.hyphenate = opts.hyphenate
        self.hyphenate_default_lang = opts.hyphenate_default_lang
        self.do_fit_images = opts.fit_images
        self.page_flip_duration = opts.page_flip_duration
        self.enable_page_flip = self.page_flip_duration > 0.1
        self.wheel_flips_pages = opts.wheel_flips_pages

    def fit_images(self):
        if self.do_fit_images:
            self.javascript('setup_image_scaling_handlers()')

    def add_window_objects(self):
        self.mainFrame().addToJavaScriptWindowObject("py_bridge", self)
        self.loaded_javascript = False

    def load_javascript_libraries(self):
        global bookmarks, referencing, hyphenation, jquery, jquery_scrollTo, \
                hyphenator, images, hyphen_pats
        if self.loaded_javascript:
            return
        self.loaded_javascript = True
        self.javascript(
            '''
            window.onresize = function(event) {
                window.py_bridge.window_resized();
            }
            ''')
        if jquery is None:
            jquery = P('content_server/jquery.js', data=True)
        self.javascript(jquery)
        if jquery_scrollTo is None:
            jquery_scrollTo = P('viewer/jquery_scrollTo.js', data=True)
        self.javascript(jquery_scrollTo)
        if bookmarks is None:
            bookmarks = P('viewer/bookmarks.js', data=True)
        self.javascript(bookmarks)
        if referencing is None:
            referencing = P('viewer/referencing.js', data=True)
        self.javascript(referencing)
        if images is None:
            images = P('viewer/images.js', data=True)
        self.javascript(images)
        if hyphenation is None:
            hyphenation = P('viewer/hyphenation.js', data=True)
        self.javascript(hyphenation)
        default_lang = self.hyphenate_default_lang
        lang = self.current_language
        if not lang:
            lang = default_lang
        def lang_name(l):
            if l == 'en':
                l = 'en-us'
            return l.lower().replace('_', '-')
        if hyphenator is None:
            hyphenator = P('viewer/hyphenate/Hyphenator.js', data=True).decode('utf-8')
        if hyphen_pats is None:
            hyphen_pats = []
            for x in glob.glob(P('viewer/hyphenate/patterns/*.js',
                allow_user_override=False)):
                with open(x, 'rb') as f:
                    hyphen_pats.append(f.read().decode('utf-8'))
            hyphen_pats = u'\n'.join(hyphen_pats)

        self.javascript(hyphenator+hyphen_pats)
        p = P('viewer/hyphenate/patterns/%s.js'%lang_name(lang))
        if not os.path.exists(p):
            lang = default_lang
            p = P('viewer/hyphenate/patterns/%s.js'%lang_name(lang))
        self.loaded_lang = lang_name(lang)

    @pyqtSignature("")
    def animated_scroll_done(self):
        self.emit(SIGNAL('animated_scroll_done()'))

    @pyqtSignature("")
    def init_hyphenate(self):
        if self.hyphenate and getattr(self, 'loaded_lang', ''):
            self.javascript('do_hyphenation("%s")'%self.loaded_lang)

    def after_load(self):
        self.set_bottom_padding(0)
        self.fit_images()
        self.init_hyphenate()

    @pyqtSignature("QString")
    def debug(self, msg):
        prints(msg)

    @pyqtSignature('')
    def window_resized(self):
        self.resize_callback()

    def reference_mode(self, enable):
        self.javascript(('enter' if enable else 'leave')+'_reference_mode()')

    def set_reference_prefix(self, prefix):
        self.javascript('reference_prefix = "%s"'%prefix)

    def goto(self, ref):
        self.javascript('goto_reference("%s")'%ref)

    def goto_bookmark(self, bm):
        bm = bm.strip()
        if bm.startswith('>'):
            bm = bm[1:].strip()
        self.javascript('scroll_to_bookmark("%s")'%bm)

    def javascript(self, string, typ=None):
        ans = self.mainFrame().evaluateJavaScript(string)
        if typ == 'int':
            ans = ans.toInt()
            if ans[1]:
                return ans[0]
            return 0
        if typ == 'string':
            return unicode(ans.toString())
        return ans

    def javaScriptConsoleMessage(self, msg, lineno, msgid):
        if self.debug_javascript:
            prints( 'JS:', msgid, lineno)
            prints(msg)
            prints(' ')
        else:
            return QWebPage.javaScriptConsoleMessage(self, msg, lineno, msgid)

    def javaScriptAlert(self, frame, msg):
        if self.debug_javascript:
            prints(msg)
        else:
            return QWebPage.javaScriptAlert(self, frame, msg)

    def scroll_by(self, dx=0, dy=0):
        self.mainFrame().scroll(dx, dy)

    def scroll_to(self, x=0, y=0):
        self.mainFrame().setScrollPosition(QPoint(x, y))

    def jump_to_anchor(self, anchor):
        self.javascript('document.location.hash = "%s"'%anchor)

    def quantize(self):
        if self.height > self.window_height:
            r = self.height%self.window_height
            if r > 0:
                self.javascript('document.body.style.paddingBottom = "%dpx"'%r)

    def element_ypos(self, elem):
        ans, ok = elem.evaluateJavaScript('$(this).offset().top').toInt()
        if not ok:
            raise ValueError('No ypos found')
        return ans

    def elem_outer_xml(self, elem):
        return unicode(elem.toOuterXml())

    def find_bookmark_element(self):
        mf = self.mainFrame()
        doc_pos = self.ypos
        min_delta, min_elem = sys.maxint, None
        for y in range(10, -500, -10):
            for x in range(-50, 500, 10):
                pos = QPoint(x, y)
                result = mf.hitTestContent(pos)
                if result.isNull(): continue
                elem = result.enclosingBlockElement()
                if elem.isNull(): continue
                try:
                    ypos = self.element_ypos(elem)
                except:
                    continue
                delta = abs(ypos - doc_pos)
                if delta < 25:
                    return elem
                if delta < min_delta:
                    min_elem, min_delta = elem, delta
        return min_elem


    def bookmark(self):
        elem = self.find_bookmark_element()

        if elem is None or self.element_ypos(elem) < 100:
            bm = 'body|%f'%(float(self.ypos)/(self.height*0.7))
        else:
            bm = unicode(elem.evaluateJavaScript(
                'calculate_bookmark(%d, this)'%self.ypos).toString())
            if not bm:
                bm = 'body|%f'%(float(self.ypos)/(self.height*0.7))
        return bm

    @property
    def at_bottom(self):
        return self.height - self.ypos <= self.window_height

    @property
    def at_top(self):
        return self.ypos <=0

    def test(self):
        pass

    @property
    def ypos(self):
        return self.mainFrame().scrollPosition().y()

    @property
    def window_height(self):
        return self.javascript('window.innerHeight', 'int')

    @property
    def window_width(self):
        return self.javascript('window.innerWidth', 'int')

    @property
    def xpos(self):
        return self.mainFrame().scrollPosition().x()

    @dynamic_property
    def scroll_fraction(self):
        def fget(self):
            try:
                return float(self.ypos)/(self.height-self.window_height)
            except ZeroDivisionError:
                return 0.
        def fset(self, val):
            npos = val * (self.height - self.window_height)
            if npos < 0:
                npos = 0
            self.scroll_to(x=self.xpos, y=npos)
        return property(fget=fget, fset=fset)

    @property
    def hscroll_fraction(self):
        try:
            return float(self.xpos)/self.width
        except ZeroDivisionError:
            return 0.

    @property
    def height(self):
        # Note that document.body.offsetHeight does not include top and bottom
        # margins on body and in some cases does not include the top margin on
        # the first element inside body either. See ticket #8791 for an example
        # of the latter.
        q = self.mainFrame().contentsSize().height()
        if q < 0:
            # Don't know if this is still needed, but it can't hurt
            j = self.javascript('document.body.offsetHeight', 'int')
            if j >= 0:
                q = j
        return q

    @property
    def width(self):
        return self.mainFrame().contentsSize().width() # offsetWidth gives inaccurate results

    def set_bottom_padding(self, amount):
        s = QSize(-1, -1) if amount == 0 else QSize(self.viewportSize().width(),
                self.height+amount)
        self.setPreferredContentsSize(s)

# }}}

class EntityDeclarationProcessor(object): # {{{

    def __init__(self, html):
        self.declared_entities = {}
        for match in re.finditer(r'<!\s*ENTITY\s+([^>]+)>', html):
            tokens = match.group(1).split()
            if len(tokens) > 1:
                self.declared_entities[tokens[0].strip()] = tokens[1].strip().replace('"', '')
        self.processed_html = html
        for key, val in self.declared_entities.iteritems():
            self.processed_html = self.processed_html.replace('&%s;'%key, val)
# }}}

class DocumentView(QWebView): # {{{

    magnification_changed = pyqtSignal(object)
    DISABLED_BRUSH = QBrush(Qt.lightGray, Qt.Dense5Pattern)

    def __init__(self, *args):
        QWebView.__init__(self, *args)
        self.flipper = SlideFlip(self)
        self.gestures = Gestures()
        self.is_auto_repeat_event = False
        self.debug_javascript = False
        self.shortcuts =  Shortcuts(SHORTCUTS, 'shortcuts/viewer')
        self.self_closing_pat = re.compile(r'<([a-z1-6]+)\s+([^>]+)/>',
                re.IGNORECASE)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self._size_hint = QSize(510, 680)
        self.initial_pos = 0.0
        self.to_bottom = False
        self.document = Document(self.shortcuts, parent=self,
                resize_callback=self.viewport_resized)
        self.setPage(self.document)
        self.manager = None
        self._reference_mode = False
        self._ignore_scrollbar_signals = False
        self.loading_url = None
        self.loadFinished.connect(self.load_finished)
        self.connect(self.document, SIGNAL('linkClicked(QUrl)'), self.link_clicked)
        self.connect(self.document, SIGNAL('linkHovered(QString,QString,QString)'), self.link_hovered)
        self.connect(self.document, SIGNAL('selectionChanged()'), self.selection_changed)
        self.connect(self.document, SIGNAL('animated_scroll_done()'),
                self.animated_scroll_done, Qt.QueuedConnection)
        copy_action = self.pageAction(self.document.Copy)
        copy_action.setIcon(QIcon(I('convert.png')))
        d = self.document
        self.unimplemented_actions = list(map(self.pageAction,
            [d.DownloadImageToDisk, d.OpenLinkInNewWindow, d.DownloadLinkToDisk,
                d.OpenImageInNewWindow, d.OpenLink]))
        self.dictionary_action = QAction(QIcon(I('dictionary.png')),
                _('&Lookup in dictionary'), self)
        self.dictionary_action.setShortcut(Qt.CTRL+Qt.Key_L)
        self.dictionary_action.triggered.connect(self.lookup)
        self.addAction(self.dictionary_action)
        self.search_action = QAction(QIcon(I('dictionary.png')),
                _('&Search for next occurrence'), self)
        self.search_action.setShortcut(Qt.CTRL+Qt.Key_S)
        self.search_action.triggered.connect(self.search_next)
        self.addAction(self.search_action)

        self.goto_location_action = QAction(_('Go to...'), self)
        self.goto_location_menu = m = QMenu(self)
        self.goto_location_actions = a = {
                'Next Page': self.next_page,
                'Previous Page': self.previous_page,
                'Section Top' : partial(self.scroll_to, 0),
                'Document Top': self.goto_document_start,
                'Section Bottom':partial(self.scroll_to, 1),
                'Document Bottom': self.goto_document_end,
                'Next Section': self.goto_next_section,
                'Previous Section': self.goto_previous_section,
        }
        for name, key in [(_('Next Section'), 'Next Section'),
                (_('Previous Section'), 'Previous Section'),
                (None, None),
                (_('Document Start'), 'Document Top'),
                (_('Document End'), 'Document Bottom'),
                (None, None),
                (_('Section Start'), 'Section Top'),
                (_('Section End'), 'Section Bottom'),
                (None, None),
                (_('Next Page'), 'Next Page'),
                (_('Previous Page'), 'Previous Page')]:
            if key is None:
                m.addSeparator()
            else:
                m.addAction(name, a[key], self.shortcuts.get_sequences(key)[0])
        self.goto_location_action.setMenu(self.goto_location_menu)

    def goto_next_section(self, *args):
        if self.manager is not None:
            self.manager.goto_next_section()

    def goto_previous_section(self, *args):
        if self.manager is not None:
            self.manager.goto_previous_section()

    def goto_document_start(self, *args):
        if self.manager is not None:
            self.manager.goto_start()

    def goto_document_end(self, *args):
        if self.manager is not None:
            self.manager.goto_end()

    @property
    def copy_action(self):
        return self.pageAction(self.document.Copy)

    def animated_scroll_done(self):
        if self.manager is not None:
            self.manager.scrolled(self.document.scroll_fraction)

    def reference_mode(self, enable):
        self._reference_mode = enable
        self.document.reference_mode(enable)

    def goto(self, ref):
        self.document.goto(ref)

    def goto_bookmark(self, bm):
        self.document.goto_bookmark(bm)

    def config(self, parent=None):
        self.document.do_config(parent)
        if self.manager is not None:
            self.manager.set_max_width()
        self.setFocus(Qt.OtherFocusReason)

    def bookmark(self):
        return self.document.bookmark()

    def selection_changed(self):
        if self.manager is not None:
            self.manager.selection_changed(unicode(self.document.selectedText()))

    def contextMenuEvent(self, ev):
        menu = self.document.createStandardContextMenu()
        for action in self.unimplemented_actions:
            menu.removeAction(action)
        text = unicode(self.selectedText())
        if text:
            menu.insertAction(list(menu.actions())[0], self.dictionary_action)
            menu.insertAction(list(menu.actions())[0], self.search_action)
        menu.addSeparator()
        menu.addAction(self.goto_location_action)
        menu.exec_(ev.globalPos())

    def lookup(self, *args):
        if self.manager is not None:
            t = unicode(self.selectedText()).strip()
            if t:
                self.manager.lookup(t.split()[0])

    def search_next(self):
        if self.manager is not None:
            t = unicode(self.selectedText()).strip()
            if t:
                self.manager.search.set_search_string(t)

    def set_manager(self, manager):
        self.manager = manager
        self.scrollbar = manager.horizontal_scrollbar
        self.connect(self.scrollbar, SIGNAL('valueChanged(int)'), self.scroll_horizontally)

    def scroll_horizontally(self, amount):
        self.document.scroll_to(y=self.document.ypos, x=amount)

    def link_hovered(self, link, text, context):
        link, text = unicode(link), unicode(text)
        if link:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()

    def link_clicked(self, url):
        if self.manager is not None:
            self.manager.link_clicked(url)

    def sizeHint(self):
        return self._size_hint

    @dynamic_property
    def scroll_fraction(self):
        def fget(self):
            return self.document.scroll_fraction
        def fset(self, val):
            self.document.scroll_fraction = float(val)
        return property(fget=fget, fset=fset)

    @property
    def hscroll_fraction(self):
        return self.document.hscroll_fraction

    @property
    def content_size(self):
        return self.document.width, self.document.height

    @dynamic_property
    def current_language(self):
        def fget(self): return self.document.current_language
        def fset(self, val): self.document.current_language = val
        return property(fget=fget, fset=fset)

    def search(self, text, backwards=False):
        if backwards:
            return self.findText(text, self.document.FindBackward)
        return self.findText(text)

    def path(self):
        return os.path.abspath(unicode(self.url().toLocalFile()))

    def self_closing_sub(self, match):
        tag = match.group(1)
        if tag.lower().strip() == 'br':
            return match.group()
        return '<%s %s></%s>'%(match.group(1), match.group(2), match.group(1))

    def load_path(self, path, pos=0.0):
        self.initial_pos = pos
        mt = getattr(path, 'mime_type', None)
        if mt is None:
            mt = guess_type(path)[0]
        html = open(path, 'rb').read().decode(path.encoding, 'replace')
        html = EntityDeclarationProcessor(html).processed_html
        has_svg = re.search(r'<[:a-zA-Z]*svg', html) is not None

        if 'xhtml' in mt:
            html = self.self_closing_pat.sub(self.self_closing_sub, html)
        if self.manager is not None:
            self.manager.load_started()
        self.loading_url = QUrl.fromLocalFile(path)
        if has_svg:
            prints('Rendering as XHTML...')
            self.setContent(QByteArray(html.encode(path.encoding)), mt, QUrl.fromLocalFile(path))
        else:
            self.setHtml(html, self.loading_url)
        self.turn_off_internal_scrollbars()

    def initialize_scrollbar(self):
        if getattr(self, 'scrollbar', None) is not None:
            delta = self.document.width - self.size().width()
            if delta > 0:
                self._ignore_scrollbar_signals = True
                self.scrollbar.blockSignals(True)
                self.scrollbar.setRange(0, delta)
                self.scrollbar.setValue(0)
                self.scrollbar.setSingleStep(1)
                self.scrollbar.setPageStep(int(delta/10.))
            self.scrollbar.setVisible(delta > 0)
            self.scrollbar.blockSignals(False)
            self._ignore_scrollbar_signals = False


    def load_finished(self, ok):
        if self.loading_url is None:
            # An <iframe> finished loading
            return
        self.loading_url = None
        self.document.load_javascript_libraries()
        self.document.after_load()
        self._size_hint = self.document.mainFrame().contentsSize()
        scrolled = False
        if self.to_bottom:
            self.to_bottom = False
            self.initial_pos = 1.0
        if self.initial_pos > 0.0:
            scrolled = True
        self.scroll_to(self.initial_pos, notify=False)
        self.initial_pos = 0.0
        self.update()
        self.initialize_scrollbar()
        self.document.reference_mode(self._reference_mode)
        if self.manager is not None:
            spine_index = self.manager.load_finished(bool(ok))
            if spine_index > -1:
                self.document.set_reference_prefix('%d.'%(spine_index+1))
            if scrolled:
                self.manager.scrolled(self.document.scroll_fraction)

        self.turn_off_internal_scrollbars()
        if self.flipper.isVisible():
            if self.flipper.running:
                self.flipper.setVisible(False)
            else:
                self.flipper(self.current_page_image(),
                        duration=self.document.page_flip_duration)


    def turn_off_internal_scrollbars(self):
        self.document.mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        self.document.mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)


    @classmethod
    def test_line(cls, img, y):
        'Test if line contains pixels of exactly the same color'
        start = img.pixel(0, y)
        for i in range(1, img.width()):
            if img.pixel(i, y) != start:
                return False
        return True

    def current_page_image(self, overlap=-1):
        if overlap < 0:
            overlap = self.height()
        img = QImage(self.width(), overlap, QImage.Format_ARGB32)
        painter = QPainter(img)
        self.document.mainFrame().render(painter, QRegion(0, 0, self.width(), overlap))
        painter.end()
        return img

    def find_next_blank_line(self, overlap):
        img = self.current_page_image(overlap)
        for i in range(overlap-1, -1, -1):
            if self.test_line(img, i):
                self.scroll_by(y=i, notify=False)
                return
        self.scroll_by(y=overlap)

    def previous_page(self):
        if self.flipper.running and not self.is_auto_repeat_event:
            return
        if self.loading_url is not None:
            return
        epf = self.document.enable_page_flip and not self.is_auto_repeat_event

        delta_y = self.document.window_height - 25
        if self.document.at_top:
            if self.manager is not None:
                self.to_bottom = True
                if epf:
                    self.flipper.initialize(self.current_page_image(), False)
                self.manager.previous_document()
        else:
            opos = self.document.ypos
            upper_limit = opos - delta_y
            if upper_limit < 0:
                upper_limit = 0
            if upper_limit < opos:
                if epf:
                    self.flipper.initialize(self.current_page_image(),
                            forwards=False)
                self.document.scroll_to(self.document.xpos, upper_limit)
                if epf:
                    self.flipper(self.current_page_image(),
                            duration=self.document.page_flip_duration)
                if self.manager is not None:
                    self.manager.scrolled(self.scroll_fraction)

    def next_page(self):
        if self.flipper.running and not self.is_auto_repeat_event:
            return
        if self.loading_url is not None:
            return
        epf = self.document.enable_page_flip and not self.is_auto_repeat_event

        window_height = self.document.window_height
        document_height = self.document.height
        ddelta = document_height - window_height
        #print '\nWindow height:', window_height
        #print 'Document height:', self.document.height

        delta_y = window_height - 25
        if self.document.at_bottom or ddelta <= 0:
            if self.manager is not None:
                if epf:
                    self.flipper.initialize(self.current_page_image())
                self.manager.next_document()
        elif ddelta < 25:
            self.scroll_by(y=ddelta)
            return
        else:
            oopos = self.document.ypos
            #print 'Original position:', oopos
            self.document.set_bottom_padding(0)
            opos = self.document.ypos
            #print 'After set padding=0:', self.document.ypos
            if opos < oopos:
                if self.manager is not None:
                    if epf:
                        self.flipper.initialize(self.current_page_image())
                    self.manager.next_document()
                return
            #oheight = self.document.height
            lower_limit = opos + delta_y # Max value of top y co-ord after scrolling
            max_y = self.document.height - window_height # The maximum possible top y co-ord
            if max_y < lower_limit:
                padding = lower_limit - max_y
                if padding == window_height:
                    if self.manager is not None:
                        if epf:
                            self.flipper.initialize(self.current_page_image())
                        self.manager.next_document()
                    return
                #print 'Setting padding to:', lower_limit - max_y
                self.document.set_bottom_padding(lower_limit - max_y)
            if epf:
                self.flipper.initialize(self.current_page_image())
            #print 'Document height:', self.document.height
            #print 'Height change:', (self.document.height - oheight)
            max_y = self.document.height - window_height
            lower_limit = min(max_y, lower_limit)
            #print 'Scroll to:', lower_limit
            if lower_limit > opos:
                self.document.scroll_to(self.document.xpos, lower_limit)
            actually_scrolled = self.document.ypos - opos
            #print 'After scroll pos:', self.document.ypos
            #print 'Scrolled by:', self.document.ypos - opos
            self.find_next_blank_line(window_height - actually_scrolled)
            #print 'After blank line pos:', self.document.ypos
            if epf:
                self.flipper(self.current_page_image(),
                        duration=self.document.page_flip_duration)
            if self.manager is not None:
                self.manager.scrolled(self.scroll_fraction)
            #print 'After all:', self.document.ypos

    def scroll_by(self, x=0, y=0, notify=True):
        old_pos = self.document.ypos
        self.document.scroll_by(x, y)
        if notify and self.manager is not None and self.document.ypos != old_pos:
            self.manager.scrolled(self.scroll_fraction)

    def scroll_to(self, pos, notify=True):
        if self._ignore_scrollbar_signals:
            return
        old_pos = self.document.ypos
        if isinstance(pos, basestring):
            self.document.jump_to_anchor(pos)
        else:
            if pos >= 1:
                self.document.scroll_to(0, self.document.height)
            else:
                y = int(math.ceil(
                        pos*(self.document.height-self.document.window_height)))
                self.document.scroll_to(0, y)
        if notify and self.manager is not None and self.document.ypos != old_pos:
            self.manager.scrolled(self.scroll_fraction)

    @dynamic_property
    def multiplier(self):
        def fget(self):
            return self.document.mainFrame().textSizeMultiplier()
        def fset(self, val):
            self.document.mainFrame().setTextSizeMultiplier(val)
            self.magnification_changed.emit(val)
        return property(fget=fget, fset=fset)

    def magnify_fonts(self):
        self.multiplier += 0.2
        return self.document.scroll_fraction

    def shrink_fonts(self):
        if self.multiplier >= 0.2:
            self.multiplier -= 0.2
        return self.document.scroll_fraction

    def changeEvent(self, event):
        if event.type() == event.EnabledChange:
            self.update()
        return QWebView.changeEvent(self, event)

    def paintEvent(self, event):
        self.turn_off_internal_scrollbars()

        painter = QPainter(self)
        self.document.mainFrame().render(painter, event.region())
        if not self.isEnabled():
            painter.fillRect(event.region().boundingRect(), self.DISABLED_BRUSH)
        painter.end()

    def wheelEvent(self, event):
        mods = event.modifiers()
        if mods & Qt.CTRL:
            if self.manager is not None and event.delta() != 0:
                f = (self.manager.font_size_larger if event.delta() > 0 else
                        self.manager.font_size_smaller)
                f(False)
            return
        if event.delta() < -14:
            if self.document.wheel_flips_pages:
                self.next_page()
                event.accept()
                return
            if self.document.at_bottom:
                self.scroll_by(y=15) # at_bottom can lie on windows
                if self.manager is not None:
                    self.manager.next_document()
                    event.accept()
                    return
        elif event.delta() > 14:
            if self.document.wheel_flips_pages:
                self.previous_page()
                event.accept()
                return

            if self.document.at_top:
                if self.manager is not None:
                    self.manager.previous_document()
                    event.accept()
                    return

        ret = QWebView.wheelEvent(self, event)

        scroll_amount = (event.delta() / 120.0) * .2 * -1
        if event.orientation() == Qt.Vertical:
            self.scroll_by(0, self.document.viewportSize().height() * scroll_amount)
        else:
            self.scroll_by(self.document.viewportSize().width() * scroll_amount, 0)

        if self.manager is not None:
            self.manager.scrolled(self.scroll_fraction)
        return ret

    def keyPressEvent(self, event):
        if not self.handle_key_press(event):
            return QWebView.keyPressEvent(self, event)

    def handle_key_press(self, event):
        handled = True
        key = self.shortcuts.get_match(event)
        func = self.goto_location_actions.get(key, None)
        if func is not None:
            self.is_auto_repeat_event = event.isAutoRepeat()
            try:
                func()
            finally:
                self.is_auto_repeat_event = False
        elif key == 'Down':
            self.scroll_by(y=15)
        elif key == 'Up':
            self.scroll_by(y=-15)
        elif key == 'Left':
            self.scroll_by(x=-15)
        elif key == 'Right':
            self.scroll_by(x=15)
        else:
            handled = False
        return handled

    def resizeEvent(self, event):
        ret = QWebView.resizeEvent(self, event)
        QTimer.singleShot(10, self.initialize_scrollbar)
        return ret

    def viewport_resized(self):
        if self.manager is not None:
            self.manager.viewport_resized(self.scroll_fraction)

    def event(self, ev):
        typ = ev.type()
        if typ == ev.TouchBegin:
            try:
                self.gestures.start_gesture('touch', ev)
            except:
                import traceback
                traceback.print_exc()
        elif typ == ev.TouchEnd:
            try:
                gesture = self.gestures.end_gesture('touch', ev, self.rect())
            except:
                import traceback
                traceback.print_exc()
            if gesture is not None:
                ev.accept()
                if gesture == 'lineleft':
                    self.next_page()
                elif gesture == 'lineright':
                    self.previous_page()
                return True
        return QWebView.event(self, ev)

    def mouseReleaseEvent(self, ev):
        opos = self.document.ypos
        ret = QWebView.mouseReleaseEvent(self, ev)
        if self.manager is not None and opos != self.document.ypos:
            self.manager.internal_link_clicked(opos)
            self.manager.scrolled(self.scroll_fraction)
        return ret

# }}}

