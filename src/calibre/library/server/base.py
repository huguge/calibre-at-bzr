#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import logging
from logging.handlers import RotatingFileHandler

import cherrypy

from calibre.constants import __appname__, __version__
from calibre.utils.date import fromtimestamp
from calibre.library.server import listen_on, log_access_file, log_error_file
from calibre.library.server.utils import expose
from calibre.utils.mdns import publish as publish_zeroconf, \
            stop_server as stop_zeroconf, get_external_ip
from calibre.library.server.content import ContentServer
from calibre.library.server.mobile import MobileServer
from calibre.library.server.xml import XMLServer
from calibre.library.server.opds import OPDSServer
from calibre.library.server.cache import Cache


class DispatchController(object): # {{{

    def __init__(self):
        self.dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.funcs = []
        self.seen = set([])

    def __call__(self, name, route, func, **kwargs):
        if name in self.seen:
            raise NameError('Route name: '+ repr(name) + ' already used')
        self.seen.add(name)
        kwargs['action'] = 'f_%d'%len(self.funcs)
        self.dispatcher.connect(name, route, self, **kwargs)
        self.funcs.append(expose(func))

    def __getattr__(self, attr):
        if not attr.startswith('f_'):
            raise AttributeError(attr + ' not found')
        num = attr.rpartition('_')[-1]
        try:
            num = int(num)
        except:
            raise AttributeError(attr + ' not found')
        if num < 0 or num >= len(self.funcs):
            raise AttributeError(attr + ' not found')
        return self.funcs[num]

# }}}

class LibraryServer(ContentServer, MobileServer, XMLServer, OPDSServer, Cache):

    server_name = __appname__ + '/' + __version__

    def __init__(self, db, opts, embedded=False, show_tracebacks=True):
        self.db = db
        for item in self.db:
            item
            break
        self.opts = opts
        self.embedded = embedded
        self.state_callback = None
        self.max_cover_width, self.max_cover_height = \
                        map(int, self.opts.max_cover.split('x'))
        path = P('content_server')
        self.build_time = fromtimestamp(os.stat(path).st_mtime)
        self.default_cover =  open(P('content_server/default_cover.jpg'), 'rb').read()
        cherrypy.config.update({
                                'log.screen'             : opts.develop,
                                'engine.autoreload_on'   : opts.develop,
                                'tools.log_headers.on'   : opts.develop,
                                'checker.on'             : opts.develop,
                                'request.show_tracebacks': show_tracebacks,
                                'server.socket_host'     : listen_on,
                                'server.socket_port'     : opts.port,
                                'server.socket_timeout'  : opts.timeout, #seconds
                                'server.thread_pool'     : opts.thread_pool, # number of threads
                               })
        if embedded:
            cherrypy.config.update({'engine.SIGHUP'          : None,
                                    'engine.SIGTERM'         : None,})
        self.config = {'global': {
            'tools.gzip.on'        : True,
            'tools.gzip.mime_types': ['text/html', 'text/plain', 'text/xml', 'text/javascript', 'text/css'],
        }}
        if opts.password:
            self.config['/'] = {
                      'tools.digest_auth.on'    : True,
                      'tools.digest_auth.realm' : (_('Password to access your calibre library. Username is ') + opts.username.strip()).encode('ascii', 'replace'),
                      'tools.digest_auth.users' : {opts.username.strip():opts.password.strip()},
                      }

        self.set_search_restriction(db.prefs.get('cs_restriction', ''))
        if opts.restriction is not None:
            self.set_search_restriction(opts.restriction)

        self.is_running = False
        self.exception = None

    def set_search_restriction(self, restriction):
        if restriction:
            self.search_restriction = 'search:'+restriction
        else:
            self.search_restriction = ''

    def setup_loggers(self):
        access_file = log_access_file
        error_file  = log_error_file
        log = cherrypy.log

        maxBytes = getattr(log, "rot_maxBytes", 10000000)
        backupCount = getattr(log, "rot_backupCount", 1000)

        # Make a new RotatingFileHandler for the error log.
        h = RotatingFileHandler(error_file, 'a', maxBytes, backupCount)
        h.setLevel(logging.DEBUG)
        h.setFormatter(cherrypy._cplogging.logfmt)
        log.error_log.addHandler(h)

        # Make a new RotatingFileHandler for the access log.
        h = RotatingFileHandler(access_file, 'a', maxBytes, backupCount)
        h.setLevel(logging.DEBUG)
        h.setFormatter(cherrypy._cplogging.logfmt)
        log.access_log.addHandler(h)

    def start(self):
        self.is_running = False
        d = DispatchController()
        for x in self.__class__.__bases__:
            if hasattr(x, 'add_routes'):
                x.add_routes(self, d)
        root_conf = self.config.get('/', {})
        root_conf['request.dispatch'] = d.dispatcher
        self.config['/'] = root_conf

        self.setup_loggers()
        cherrypy.tree.mount(root=None, config=self.config)
        try:
            try:
                cherrypy.engine.start()
            except:
                ip = get_external_ip()
                if not ip or ip == '127.0.0.1':
                    raise
                cherrypy.log('Trying to bind to single interface: '+ip)
                cherrypy.config.update({'server.socket_host' : ip})
                cherrypy.engine.start()

            self.is_running = True
            try:
                publish_zeroconf('Books in calibre', '_stanza._tcp',
                             self.opts.port, {'path':'/stanza'})
            except:
                import traceback
                cherrypy.log.error('Failed to start BonJour:')
                cherrypy.log.error(traceback.format_exc())
            cherrypy.engine.block()
        except Exception, e:
            self.exception = e
        finally:
            self.is_running = False
            try:
                stop_zeroconf()
            except:
                import traceback
                cherrypy.log.error('Failed to stop BonJour:')
                cherrypy.log.error(traceback.format_exc())
            try:
                if callable(self.state_callback):
                    self.state_callback(self.is_running)
            except:
                pass

    def exit(self):
        try:
            cherrypy.engine.exit()
        finally:
            cherrypy.server.httpserver = None
            self.is_running = False
            try:
                if callable(self.state_callback):
                    self.state_callback(self.is_running)
            except:
                pass


