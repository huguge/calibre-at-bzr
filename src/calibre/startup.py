__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Perform various initialization tasks.
'''

import locale, sys, os, re, cStringIO
from gettext import GNUTranslations

# Default translation is NOOP
import __builtin__
__builtin__.__dict__['_'] = lambda s: s

# For strings which belong in the translation tables, but which shouldn't be
# immediately translated to the environment language
__builtin__.__dict__['__'] = lambda s: s

from calibre.constants import iswindows, preferred_encoding, plugins
from calibre.utils.config import prefs
from calibre.translations.msgfmt import make

_run_once = False
if not _run_once:
    _run_once = True

    ################################################################################
    # Setup translations

    def get_lang():
        lang = prefs['language']
        if lang is not None:
            return lang
        lang = locale.getdefaultlocale(['LANGUAGE', 'LC_ALL', 'LC_CTYPE',
                                       'LC_MESSAGES', 'LANG'])[0]
        if lang is None and os.environ.has_key('LANG'): # Needed for OS X
            try:
                lang = os.environ['LANG']
            except:
                pass
        if lang:
            match = re.match('[a-z]{2,3}', lang)
            if match:
                lang = match.group()
        return lang

    def set_translator():
        # To test different translations invoke as
        # LC_ALL=de_DE.utf8 program
        try:
            from calibre.translations.compiled import translations
        except:
            return
        lang = get_lang()
        if lang:
            buf = None
            if os.access(lang+'.po', os.R_OK):
                buf = cStringIO.StringIO()
                make(lang+'.po', buf)
                buf = cStringIO.StringIO(buf.getvalue())
            elif translations.has_key(lang):
                buf = cStringIO.StringIO(translations[lang])
            if buf is not None:
                t = GNUTranslations(buf)
                t.install(unicode=True)

    set_translator()

    ################################################################################
    # Initialize locale
    try:
        locale.setlocale(locale.LC_ALL, '')
    except:
        dl = locale.getdefaultlocale()
        try:
            if dl:
                locale.setlocale(dl[0])
        except:
            pass

    ################################################################################
    # Improve builtin path functions to handle unicode sensibly

    _abspath = os.path.abspath
    def my_abspath(path, encoding=sys.getfilesystemencoding()):
        '''
        Work around for buggy os.path.abspath. This function accepts either byte strings,
        in which it calls os.path.abspath, or unicode string, in which case it first converts
        to byte strings using `encoding`, calls abspath and then decodes back to unicode.
        '''
        to_unicode = False
        if encoding is None:
            encoding = preferred_encoding
        if isinstance(path, unicode):
            path = path.encode(encoding)
            to_unicode = True
        res = _abspath(path)
        if to_unicode:
            res = res.decode(encoding)
        return res

    os.path.abspath = my_abspath
    _join = os.path.join
    def my_join(a, *p):
        encoding=sys.getfilesystemencoding()
        if not encoding:
            encoding = preferred_encoding
        p = [a] + list(p)
        _unicode = False
        for i in p:
            if isinstance(i, unicode):
                _unicode = True
                break
        p = [i.encode(encoding) if isinstance(i, unicode) else i for i in p]

        res = _join(*p)
        if _unicode:
            res = res.decode(encoding)
        return res

    os.path.join = my_join


    ################################################################################
    # Platform specific modules
    winutil = winutilerror = None
    if iswindows:
        winutil, winutilerror = plugins['winutil']
        if not winutil:
            raise RuntimeError('Failed to load the winutil plugin: %s'%winutilerror)
        if len(sys.argv) > 1:
            sys.argv[1:] = winutil.argv()[1-len(sys.argv):]

    ################################################################################
    # Convert command line arguments to unicode
    for i in range(1, len(sys.argv)):
        if not isinstance(sys.argv[i], unicode):
            sys.argv[i] = sys.argv[i].decode(preferred_encoding, 'replace')
