#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import Qt

from calibre.gui2 import Dispatcher
from calibre.gui2.tools import fetch_scheduled_recipe
from calibre.utils.config import dynamic
from calibre.gui2.actions import InterfaceAction

class FetchNewsAction(InterfaceAction):

    name = 'Fetch News'
    action_spec = (_('Fetch news'), 'news.svg', None, _('F'))

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def genesis(self):
        self.conversion_jobs = {}

    def init_scheduler(self, db):
        from calibre.gui2.dialogs.scheduler import Scheduler
        self.scheduler = Scheduler(self.gui, db)
        self.scheduler.start_recipe_fetch.connect(self.download_scheduled_recipe, type=Qt.QueuedConnection)
        self.qaction.setMenu(self.scheduler.news_menu)
        self.qaction.triggered.connect(
                self.scheduler.show_dialog)
        self.database_changed = self.scheduler.database_changed

    def connect_scheduler(self):
        self.scheduler.delete_old_news.connect(
                self.gui.library_view.model().delete_books_by_id,
                type=Qt.QueuedConnection)

    def download_scheduled_recipe(self, arg):
        func, args, desc, fmt, temp_files = \
                fetch_scheduled_recipe(arg)
        job = self.gui.job_manager.run_job(
                Dispatcher(self.scheduled_recipe_fetched), func, args=args,
                           description=desc)
        self.conversion_jobs[job] = (temp_files, fmt, arg)
        self.gui.status_bar.show_message(_('Fetching news from ')+arg['title'], 2000)

    def scheduled_recipe_fetched(self, job):
        temp_files, fmt, arg = self.conversion_jobs.pop(job)
        pt = temp_files[0]
        if job.failed:
            self.gui.scheduler.recipe_download_failed(arg)
            return self.gui.job_exception(job)
        id = self.gui.library_view.model().add_news(pt.name, arg)
        self.gui.library_view.model().reset()
        sync = dynamic.get('news_to_be_synced', set([]))
        sync.add(id)
        dynamic.set('news_to_be_synced', sync)
        self.gui.scheduler.recipe_downloaded(arg)
        self.gui.status_bar.show_message(arg['title'] + _(' fetched.'), 3000)
        self.gui.email_news(id)
        self.gui.sync_news()


