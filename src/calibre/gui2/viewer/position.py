#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json

class PagePosition(object):

    def __init__(self, document):
        self.document = document

    @property
    def viewport_cfi(self):
        ans = None
        res = self.document.mainFrame().evaluateJavaScript('''
            ans = 'undefined';
            try {
                ans = window.cfi.at_current();
                if (!ans) ans = 'undefined';
            } catch (err) {
                window.console.log(err);
            }
            window.console.log("Viewport cfi: " + ans);
            ans;
        ''')
        if res.isValid() and not res.isNull() and res.type() == res.String:
            c = unicode(res.toString())
            if c != 'undefined':
                ans = c
        return ans

    def scroll_to_cfi(self, cfi):
        if cfi:
            cfi = json.dumps(cfi)
            self.document.mainFrame().evaluateJavaScript('''
                    function fix_scroll() {
                        /* cfi.scroll_to() uses scrollIntoView() which can result
                           in scrolling along the x-axis. So we
                           explicitly scroll to x=0.
                        */
                       scrollTo(0, window.pageYOffset)
                    }

                    window.cfi.scroll_to(%s, fix_scroll);
                '''%cfi)

    @property
    def current_pos(self):
        ans = self.viewport_cfi
        if not ans:
            ans = self.document.scroll_fraction
        return ans

    def __enter__(self):
        self.save()

    def __exit__(self, *args):
        self.restore()

    def save(self):
        self._cpos = self.current_pos

    def restore(self):
        if self._cpos is None: return
        if isinstance(self._cpos, (int, float)):
            self.document.scroll_fraction = self._cpos
        else:
            self.scroll_to_cfi(self._cpos)
        self._cpos = None


