#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.utils.config import Config, StringConfig, config_dir


listen_on = '0.0.0.0'


log_access_file = os.path.join(config_dir, 'server_access_log.txt')
log_error_file = os.path.join(config_dir, 'server_error_log.txt')


def server_config(defaults=None):
    desc=_('Settings to control the calibre content server')
    c = Config('server', desc) if defaults is None else StringConfig(defaults, desc)

    c.add_opt('port', ['-p', '--port'], default=8080,
              help=_('The port on which to listen. Default is %default'))
    c.add_opt('timeout', ['-t', '--timeout'], default=120,
              help=_('The server timeout in seconds. Default is %default'))
    c.add_opt('thread_pool', ['--thread-pool'], default=30,
              help=_('The max number of worker threads to use. Default is %default'))
    c.add_opt('password', ['--password'], default=None,
              help=_('Set a password to restrict access. By default access is unrestricted.'))
    c.add_opt('username', ['--username'], default='calibre',
              help=_('Username for access. By default, it is: %default'))
    c.add_opt('develop', ['--develop'], default=False,
              help='Development mode. Server automatically restarts on file changes and serves code files (html, css, js) from the file system instead of calibre\'s resource system.')
    c.add_opt('max_cover', ['--max-cover'], default='600x800',
              help=_('The maximum size for displayed covers. Default is %default.'))
    c.add_opt('max_opds_items', ['--max-opds-items'], default=30,
            help=_('The maximum number of matches to return per OPDS query. '
            'This affects Stanza, WordPlayer, etc. integration.'))
    return c

