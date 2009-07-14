__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__appname__   = 'calibre'
__version__   = '0.6.0b13'
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"

import re
_ver = __version__.split('.')
_ver = [int(re.search(r'(\d+)', x).group(1)) for x in _ver]
numeric_version = tuple(_ver)

'''
Various run time constants.
'''

import sys, locale, codecs, os
from calibre.utils.terminfo import TerminalController

terminal_controller = TerminalController(sys.stdout)

iswindows = 'win32' in sys.platform.lower() or 'win64' in sys.platform.lower()
isosx     = 'darwin' in sys.platform.lower()
islinux   = not(iswindows or isosx)
isfrozen  = hasattr(sys, 'frozen')

try:
    preferred_encoding = locale.getpreferredencoding()
    codecs.lookup(preferred_encoding)
except:
    preferred_encoding = 'utf-8'

win32event = __import__('win32event') if iswindows else None
winerror   = __import__('winerror') if iswindows else None
win32api   = __import__('win32api') if iswindows else None
fcntl      = None if iswindows else __import__('fcntl')

filesystem_encoding = sys.getfilesystemencoding()
if filesystem_encoding is None: filesystem_encoding = 'utf-8'


################################################################################
plugins = None
if plugins is None:
    # Load plugins
    def load_plugins():
        plugins = {}
        if isfrozen:
            if iswindows:
                plugin_path = os.path.join(os.path.dirname(sys.executable), 'plugins')
                sys.path.insert(1, os.path.dirname(sys.executable))
            elif isosx:
                plugin_path = os.path.join(getattr(sys, 'frameworks_dir'), 'plugins')
            elif islinux:
                plugin_path = os.path.join(getattr(sys, 'frozen_path'), 'plugins')
            sys.path.insert(0, plugin_path)
        else:
            import pkg_resources
            plugin_path = getattr(pkg_resources, 'resource_filename')('calibre', 'plugins')
            sys.path.insert(0, plugin_path)

        for plugin in ['pictureflow', 'lzx', 'msdes', 'podofo', 'cPalmdoc',
            'fontconfig'] + \
                    (['winutil'] if iswindows else []) + \
                    (['usbobserver'] if isosx else []):
            try:
                p, err = __import__(plugin), ''
            except Exception, err:
                p = None
                err = str(err)
            plugins[plugin] = (p, err)
        return plugins

    plugins = load_plugins()
