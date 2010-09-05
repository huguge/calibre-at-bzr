#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time

import cherrypy

from calibre import strftime as _strftime, prints
from calibre.utils.date import now as nowf
from calibre.utils.config import tweaks


def expose(func):

    def do(*args, **kwargs):
        self = func.im_self
        if self.opts.develop:
            start = time.time()

        dict.update(cherrypy.response.headers, {'Server':self.server_name})
        if not self.embedded:
            self.db.check_if_modified()
        ans = func(*args, **kwargs)
        if self.opts.develop:
            prints('Function', func.__name__, 'called with args:', args, kwargs)
            prints('\tTime:', func.__name__, time.time()-start)
        return ans

    do.__name__ = func.__name__

    return do


def strftime(fmt='%Y/%m/%d %H:%M:%S', dt=None):
    if not hasattr(dt, 'timetuple'):
        dt = nowf()
    dt = dt.timetuple()
    try:
        return _strftime(fmt, dt)
    except:
        return _strftime(fmt, nowf().timetuple())

def format_tag_string(tags, sep):
    MAX = tweaks['max_content_server_tags_shown']
    if tags:
        tlist = [t.strip() for t in tags.split(sep)]
    else:
        tlist = []
    tlist.sort(cmp=lambda x,y:cmp(x.lower(), y.lower()))
    if len(tlist) > MAX:
        tlist = tlist[:MAX]+['...']
    return u'%s'%(', '.join(tlist)) if tlist else ''

