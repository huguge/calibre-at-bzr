#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import absolute_import

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, locale, re, cStringIO, cPickle
from gettext import GNUTranslations, NullTranslations
from zipfile import ZipFile

_available_translations = None

def available_translations():
    global _available_translations
    if _available_translations is None:
        stats = P('localization/stats.pickle', allow_user_override=False)
        if os.path.exists(stats):
            stats = cPickle.load(open(stats, 'rb'))
        else:
            stats = {}
        _available_translations = [x for x in stats if stats[x] > 0.1]
    return _available_translations

def get_lang():
    'Try to figure out what language to display the interface in'
    from calibre.utils.config_base import prefs
    lang = prefs['language']
    lang = os.environ.get('CALIBRE_OVERRIDE_LANG', lang)
    if lang is not None:
        return lang
    try:
        lang = locale.getdefaultlocale(['LANGUAGE', 'LC_ALL', 'LC_CTYPE',
                                    'LC_MESSAGES', 'LANG'])[0]
    except:
        pass # This happens on Ubuntu apparently
    if lang is None and os.environ.has_key('LANG'): # Needed for OS X
        try:
            lang = os.environ['LANG']
        except:
            pass
    if lang:
        match = re.match('[a-z]{2,3}(_[A-Z]{2}){0,1}', lang)
        if match:
            lang = match.group()
    if lang == 'zh':
        lang = 'zh_CN'
    if lang is None:
        lang = 'en'
    return lang

def get_lc_messages_path(lang):
    hlang = None
    if zf_exists():
        if lang in available_translations():
            hlang = lang
        else:
            xlang = lang.split('_')[0]
            if xlang in available_translations():
                hlang = xlang
    return hlang

def zf_exists():
    return os.path.exists(P('localization/locales.zip',
                allow_user_override=False))

def set_translators():
    # To test different translations invoke as
    # CALIBRE_OVERRIDE_LANG=de_DE.utf8 program
    lang = get_lang()
    if lang:
        buf = iso639 = None
        mpath = get_lc_messages_path(lang)
        if os.access(mpath+'.po', os.R_OK):
            from calibre.translations.msgfmt import make
            buf = cStringIO.StringIO()
            make(mpath+'.po', buf)
            buf = cStringIO.StringIO(buf.getvalue())

        if mpath is not None:
            with ZipFile(P('localization/locales.zip',
                allow_user_override=False), 'r') as zf:
                if buf is None:
                    buf = cStringIO.StringIO(zf.read(mpath + '/messages.mo'))
                if mpath == 'nds':
                    mpath = 'de'
                isof = mpath + '/iso639.mo'
                try:
                    iso639 = cStringIO.StringIO(zf.read(isof))
                except:
                    pass # No iso639 translations for this lang

        t = None
        if buf is not None:
            t = GNUTranslations(buf)
            if iso639 is not None:
                iso639 = GNUTranslations(iso639)
                t.add_fallback(iso639)

        if t is None:
            t = NullTranslations()

        t.install(unicode=True, names=('ngettext',))

_iso639 = None
_extra_lang_codes = {
        'pt_BR' : _('Brazilian Portuguese'),
        'en_GB' : _('English (UK)'),
        'zh_CN' : _('Simplified Chinese'),
        'zh_HK' : _('Chinese (HK)'),
        'zh_TW' : _('Traditional Chinese'),
        'en'    : _('English'),
        'en_AU' : _('English (Australia)'),
        'en_NZ' : _('English (New Zealand)'),
        'en_CA' : _('English (Canada)'),
        'en_GR' : _('English (Greece)'),
        'en_IN' : _('English (India)'),
        'en_TH' : _('English (Thailand)'),
        'en_TR' : _('English (Turkey)'),
        'en_CY' : _('English (Cyprus)'),
        'en_CZ' : _('English (Czechoslovakia)'),
        'en_PK' : _('English (Pakistan)'),
        'en_HR' : _('English (Croatia)'),
        'en_ID' : _('English (Indonesia)'),
        'en_IL' : _('English (Israel)'),
        'en_SG' : _('English (Singapore)'),
        'en_YE' : _('English (Yemen)'),
        'en_IE' : _('English (Ireland)'),
        'en_CN' : _('English (China)'),
        'en_ZA' : _('English (South Africa)'),
        'es_PY' : _('Spanish (Paraguay)'),
        'es_UY' : _('Spanish (Uruguay)'),
        'es_AR' : _('Spanish (Argentina)'),
        'es_MX' : _('Spanish (Mexico)'),
        'es_CU' : _('Spanish (Cuba)'),
        'es_CL' : _('Spanish (Chile)'),
        'es_EC' : _('Spanish (Ecuador)'),
        'es_HN' : _('Spanish (Honduras)'),
        'es_VE' : _('Spanish (Venezuela)'),
        'es_BO' : _('Spanish (Bolivia)'),
        'es_NI' : _('Spanish (Nicaragua)'),
        'de_AT' : _('German (AT)'),
        'fr_BE' : _('French (BE)'),
        'nl'    : _('Dutch (NL)'),
        'nl_BE' : _('Dutch (BE)'),
        'und'   : _('Unknown')
        }

if False:
    # Extra strings needed for Qt

    # NOTE: Ante Meridian (i.e. like 10:00 AM)
    _('AM')
    # NOTE: Post Meridian (i.e. like 10:00 PM)
    _('PM')
    # NOTE: Ante Meridian (i.e. like 10:00 am)
    _('am')
    # NOTE: Post Meridian (i.e. like 10:00 pm)
    _('pm')

_lcase_map = {}
for k in _extra_lang_codes:
    _lcase_map[k.lower()] = k

def get_language(lang):
    global _iso639
    translate = _
    lang = _lcase_map.get(lang, lang)
    if lang in _extra_lang_codes:
        # The translator was not active when _extra_lang_codes was defined, so
        # re-translate
        return translate(_extra_lang_codes[lang])
    ip = P('localization/iso639.pickle')
    if not os.path.exists(ip):
        return lang
    if _iso639 is None:
        _iso639 = cPickle.load(open(ip, 'rb'))
    ans = lang
    lang = lang.split('_')[0].lower()
    if len(lang) == 2:
        ans = _iso639['by_2'].get(lang, ans)
    elif len(lang) == 3:
        if lang in _iso639['by_3b']:
            ans = _iso639['by_3b'][lang]
        else:
            ans = _iso639['by_3t'].get(lang, ans)
    return translate(ans)


_udc = None

def get_udc():
    global _udc
    if _udc is None:
        from calibre.ebooks.unihandecode import Unihandecoder
        _udc = Unihandecoder(lang=get_lang())
    return _udc


