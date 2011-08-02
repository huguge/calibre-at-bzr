#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import random

from calibre.gui2.actions import InterfaceAction

class PickRandomAction(InterfaceAction):

    name = 'Pick Random Book'
    action_spec = (_('Pick a random book'), 'random.png', 'Catalog builder', None)
    dont_add_to = frozenset(['menubar-device', 'toolbar-device', 'context-menu-device'])

    def genesis(self):
        self.qaction.triggered.connect(self.pick_random)

    def pick_random(self):
        pick = random.randint(0, self.gui.library_view.model().rowCount(None))
        self.gui.library_view.set_current_row(pick)
        self.gui.library_view.scroll_to_row(pick)


