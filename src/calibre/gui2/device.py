from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, traceback, Queue, time, socket
from threading import Thread, RLock
from itertools import repeat
from functools import partial
from binascii import unhexlify

from PyQt4.Qt import QMenu, QAction, QActionGroup, QIcon, SIGNAL, QPixmap, \
                     Qt

from calibre.devices import devices
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.parallel import Job
from calibre.devices.scanner import DeviceScanner
from calibre.gui2 import config, error_dialog, Dispatcher, dynamic, \
                                   pixmap_to_data, warning_dialog
from calibre.ebooks.metadata import authors_to_string
from calibre.gui2.dialogs.conversion_error import ConversionErrorDialog
from calibre.devices.interface import Device
from calibre import sanitize_file_name, preferred_encoding
from calibre.utils.filenames import ascii_filename
from calibre.devices.errors import FreeSpaceError
from calibre.utils.smtp import compose_mail, sendmail, extract_email_address, \
        config as email_config

class DeviceJob(Job):

    def __init__(self, func, *args, **kwargs):
        Job.__init__(self, *args, **kwargs)
        self.func = func

    def run(self):
        self.start_work()
        try:
            self.result = self.func(*self.args, **self.kwargs)
        except (Exception, SystemExit), err:
            self.exception = err
            self.traceback = traceback.format_exc()
        finally:
            self.job_done()


class DeviceManager(Thread):

    def __init__(self, connected_slot, job_manager, sleep_time=2):
        '''
        @param sleep_time: Time to sleep between device probes in millisecs
        @type sleep_time: integer
        '''
        Thread.__init__(self)
        self.setDaemon(True)
        self.devices        = [[d, False] for d in devices()]
        self.device         = None
        self.device_class   = None
        self.sleep_time     = sleep_time
        self.connected_slot = connected_slot
        self.jobs           = Queue.Queue(0)
        self.keep_going     = True
        self.job_manager    = job_manager
        self.current_job    = None
        self.scanner        = DeviceScanner()

    def detect_device(self):
        self.scanner.scan()
        for device in self.devices:
            connected = self.scanner.is_device_connected(device[0])
            if connected and not device[1]:
                try:
                    dev = device[0]()
                    dev.open()
                    self.device       = dev
                    self.device_class = dev.__class__
                    self.connected_slot(True)
                except:
                    print 'Unable to open device'
                    traceback.print_exc()
                finally:
                    device[1] = True
            elif not connected and device[1]:
                while True:
                    try:
                        job = self.jobs.get_nowait()
                        job.abort(Exception(_('Device no longer connected.')))
                    except Queue.Empty:
                        break
                self.device = None
                self.connected_slot(False)
                device[1] ^= True

    def next(self):
        if not self.jobs.empty():
            try:
                return self.jobs.get_nowait()
            except Queue.Empty:
                pass

    def run(self):
        while self.keep_going:
            self.detect_device()
            while True:
                job = self.next()
                if job is not None:
                    self.current_job = job
                    self.device.set_progress_reporter(job.update_status)
                    self.current_job.run()
                    self.current_job = None
                else:
                    break
            time.sleep(self.sleep_time)

    def create_job(self, func, done, description, args=[], kwargs={}):
        job = DeviceJob(func, done, self.job_manager,
                        args=args, kwargs=kwargs, description=description)
        self.job_manager.add_job(job)
        self.jobs.put(job)
        return job

    def has_card(self):
        try:
            return bool(self.device.card_prefix())
        except:
            return False

    def _get_device_information(self):
        info = self.device.get_device_information(end_session=False)
        info = [i.replace('\x00', '').replace('\x01', '') for i in info]
        cp = self.device.card_prefix(end_session=False)
        fs = self.device.free_space()
        return info, cp, fs

    def get_device_information(self, done):
        '''Get device information and free space on device'''
        return self.create_job(self._get_device_information, done,
                    description=_('Get device information'))

    def _books(self):
        '''Get metadata from device'''
        mainlist = self.device.books(oncard=False, end_session=False)
        cardlist = self.device.books(oncard=True)
        return (mainlist, cardlist)

    def books(self, done):
        '''Return callable that returns the list of books on device as two booklists'''
        return self.create_job(self._books, done, description=_('Get list of books on device'))

    def _sync_booklists(self, booklists):
        '''Sync metadata to device'''
        self.device.sync_booklists(booklists, end_session=False)
        return self.device.card_prefix(end_session=False), self.device.free_space()

    def sync_booklists(self, done, booklists):
        return self.create_job(self._sync_booklists, done, args=[booklists],
                        description=_('Send metadata to device'))

    def _upload_books(self, files, names, on_card=False, metadata=None):
        '''Upload books to device: '''
        return self.device.upload_books(files, names, on_card,
                                        metadata=metadata, end_session=False)

    def upload_books(self, done, files, names, on_card=False, titles=None,
                     metadata=None):
        desc = _('Upload %d books to device')%len(names)
        if titles:
            desc += u':' + u', '.join(titles)
        return self.create_job(self._upload_books, done, args=[files, names],
                kwargs={'on_card':on_card,'metadata':metadata}, description=desc)

    def add_books_to_metadata(self, locations, metadata, booklists):
        self.device.add_books_to_metadata(locations, metadata, booklists)

    def _delete_books(self, paths):
        '''Remove books from device'''
        self.device.delete_books(paths, end_session=True)

    def delete_books(self, done, paths):
        return self.create_job(self._delete_books, done, args=[paths],
                        description=_('Delete books from device'))

    def remove_books_from_metadata(self, paths, booklists):
        self.device.remove_books_from_metadata(paths, booklists)

    def _save_books(self, paths, target):
        '''Copy books from device to disk'''
        for path in paths:
            name = path.rpartition('/')[2]
            f = open(os.path.join(target, name), 'wb')
            self.device.get_file(path, f)
            f.close()

    def save_books(self, done, paths, target):
        return self.create_job(self._save_books, done, args=[paths, target],
                        description=_('Download books from device'))

    def _view_book(self, path, target):
        f = open(target, 'wb')
        self.device.get_file(path, f)
        f.close()
        return target

    def view_book(self, done, path, target):
        return self.create_job(self._view_book, done, args=[path, target],
                        description=_('View book on device'))


class DeviceAction(QAction):

    def __init__(self, dest, delete, specific, icon_path, text, parent=None):
        if delete:
            text += ' ' + _('and delete from library')
        QAction.__init__(self, QIcon(icon_path), text, parent)
        self.dest = dest
        self.delete = delete
        self.specific = specific
        self.connect(self, SIGNAL('triggered(bool)'),
                lambda x : self.emit(SIGNAL('a_s(QAction)'), self))

    def __repr__(self):
        return self.__class__.__name__ + ':%s:%s:%s'%(self.dest, self.delete,
                self.specific)


class DeviceMenu(QMenu):

    def __init__(self, parent=None):
        QMenu.__init__(self, parent)
        self.group = QActionGroup(self)
        self.actions = []
        self._memory = []

        self.set_default_menu = self.addMenu(_('Set default send to device'
            ' action'))
        opts = email_config().parse()
        default_account = None
        if opts.accounts:
            self.email_to_menu = self.addMenu(_('Email to')+'...')
            keys = sorted(opts.accounts.keys())
            for account in keys:
                formats, auto, default = opts.accounts[account]
                dest = 'mail:'+account+';'+formats
                if default:
                    default_account = (dest, False, False, ':/images/mail.svg',
                            _('Email to')+' '+account)
                action1 = DeviceAction(dest, False, False, ':/images/mail.svg',
                        _('Email to')+' '+account, self)
                action2 = DeviceAction(dest, True, False, ':/images/mail.svg',
                        _('Email to')+' '+account, self)
                map(self.email_to_menu.addAction, (action1, action2))
                map(self._memory.append, (action1, action2))
                self.email_to_menu.addSeparator()
                self.connect(action1, SIGNAL('a_s(QAction)'),
                            self.action_triggered)
                self.connect(action2, SIGNAL('a_s(QAction)'),
                            self.action_triggered)




        _actions = [
                ('main:', False, False,  ':/images/reader.svg',
                    _('Send to main memory')),
                ('card:0', False, False, ':/images/sd.svg',
                    _('Send to storage card')),
                '-----',
                ('main:', True, False,   ':/images/reader.svg',
                    _('Send to main memory')),
                ('card:0', True, False,  ':/images/sd.svg',
                    _('Send to storage card')),
                '-----',
                ('main:', False, True,  ':/images/reader.svg',
                    _('Send specific format to main memory')),
                ('card:0', False, True, ':/images/sd.svg',
                    _('Send specific format to storage card')),

                ]
        if default_account is not None:
            _actions.insert(2, default_account)
            _actions.insert(6, list(default_account))
            _actions[6][1] = True
        for round in (0, 1):
            for dest, delete, specific, icon, text in _actions:
                if dest == '-':
                    (self.set_default_menu if round else self).addSeparator()
                    continue
                action = DeviceAction(dest, delete, specific, icon, text, self)
                self._memory.append(action)
                if round == 1:
                    action.setCheckable(True)
                    action.setText(action.text())
                    self.group.addAction(action)
                    self.set_default_menu.addAction(action)
                else:
                    self.connect(action, SIGNAL('a_s(QAction)'),
                            self.action_triggered)
                    self.actions.append(action)
                    self.addAction(action)


        da = config['default_send_to_device_action']
        done = False
        for action in self.group.actions():
            if repr(action) == da:
                action.setChecked(True)
                done = True
                break
        if not done:
            action = list(self.group.actions())[0]
            action.setChecked(True)
            config['default_send_to_device_action'] = repr(action)

        self.connect(self.group, SIGNAL('triggered(QAction*)'),
                self.change_default_action)
        self.enable_device_actions(False)
        if opts.accounts:
            self.addSeparator()
            self.addMenu(self.email_to_menu)

    def change_default_action(self, action):
        config['default_send_to_device_action'] = repr(action)
        action.setChecked(True)

    def action_triggered(self, action):
        self.emit(SIGNAL('sync(PyQt_PyObject, PyQt_PyObject, PyQt_PyObject)'),
                action.dest, action.delete, action.specific)

    def trigger_default(self, *args):
        r = config['default_send_to_device_action']
        for action in self.actions:
            if repr(action) == r:
                self.action_triggered(action)
                break

    def enable_device_actions(self, enable):
        for action in self.actions:
            if action.dest[:4] in ('main', 'card'):
                action.setEnabled(enable)

class Emailer(Thread):

    def __init__(self, timeout=60):
        Thread.__init__(self)
        self.setDaemon(True)
        self.job_lock = RLock()
        self.jobs = []
        self._run = True
        self.timeout = timeout

    def run(self):
        while self._run:
            job = None
            with self.job_lock:
                if self.jobs:
                    job = self.jobs[0]
                    self.jobs = self.jobs[1:]
            if job is not None:
                self._send_mails(*job)
            time.sleep(1)

    def stop(self):
        self._run = False

    def send_mails(self, jobnames, callback, attachments, to_s, subjects,
                  texts, attachment_names):
        job = (jobnames, callback, attachments, to_s, subjects, texts,
                attachment_names)
        with self.job_lock:
            self.jobs.append(job)

    def _send_mails(self, jobnames, callback, attachments,
                    to_s, subjects, texts, attachment_names):
        opts = email_config().parse()
        opts.verbose = 3 if os.environ.get('CALIBRE_DEBUG_EMAIL', False) else 0
        from_ = opts.from_
        if not from_:
            from_ = 'calibre <calibre@'+socket.getfqdn()+'>'
        results = []
        for i, jobname in enumerate(jobnames):
            try:
                msg = compose_mail(from_, to_s[i], texts[i], subjects[i],
                        open(attachments[i], 'rb'),
                        attachment_name = attachment_names[i])
                efrom, eto = map(extract_email_address, (from_, to_s[i]))
                eto = [eto]
                sendmail(msg, efrom, eto, localhost=None,
                            verbose=opts.verbose,
                            timeout=self.timeout, relay=opts.relay_host,
                            username=opts.relay_username,
                            password=unhexlify(opts.relay_password), port=opts.relay_port,
                            encryption=opts.encryption)
                results.append([jobname, None, None])
            except Exception, e:
                results.append([jobname, e, traceback.format_exc()])
        callback(results)


class DeviceGUI(object):

    def dispatch_sync_event(self, dest, delete, specific):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            error_dialog(self, _('No books'), _('No books')+' '+\
                    _('selected to send')).exec_()
            return

        fmt = None
        if specific:
            d = ChooseFormatDialog(self, _('Choose format to send to device'),
                                self.device_manager.device_class.FORMATS)
            d.exec_()
            fmt = d.format().lower()
        dest, sub_dest = dest.split(':')
        if dest in ('main', 'card'):
            if not self.device_connected or not self.device_manager:
                error_dialog(self, _('No device'),
                        _('Cannot send: No device is connected')).exec_()
                return
            on_card = dest == 'card'
            if on_card and not self.device_manager.has_card():
                error_dialog(self, _('No card'),
                        _('Cannot send: Device has no storage card')).exec_()
                return
            self.sync_to_device(on_card, delete, fmt)
        elif dest == 'mail':
            to, fmts = sub_dest.split(';')
            fmts = [x.strip().lower() for x in fmts.split(',')]
            self.send_by_mail(to, fmts, delete)

    def send_by_mail(self, to, fmts, delete_from_library):
        rows = self.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return
        ids = iter(self.library_view.model().id(r) for r in rows)
        full_metadata = self.library_view.model().get_metadata(
                                        rows, full_metadata=True)[-1]
        files = self.library_view.model().get_preferred_formats(rows,
                                    fmts, paths=True, set_metadata=True)
        files = [getattr(f, 'name', None) for f in files]

        bad, remove_ids, jobnames = [], [], []
        texts, subjects, attachments, attachment_names = [], [], [], []
        for f, mi, id in zip(files, full_metadata, ids):
            t = mi.title
            if not t:
                t = _('Unknown')
            if f is None:
                bad.append(t)
            else:
                remove_ids.append(id)
                jobnames.append(u'%s:%s'%(id, t))
                attachments.append(f)
                subjects.append(_('E-book:')+ ' '+t)
                a = authors_to_string(mi.authors if mi.authors else \
                        [_('Unknown')])
                texts.append(_('Attached, you will find the e-book') + \
                        '\n\n' + t + '\n\t' + _('by') + ' ' + a + '\n\n' + \
                        _('in the %s format.') %
                        os.path.splitext(f)[1][1:].upper())
                prefix = sanitize_file_name(t+' - '+a)
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                attachment_names.append(prefix + os.path.splitext(f)[1])
        remove = remove_ids if delete_from_library else []

        to_s = list(repeat(to, len(attachments)))
        if attachments:
            self.emailer.send_mails(jobnames,
                    Dispatcher(partial(self.emails_sent, remove=remove)),
                    attachments, to_s, subjects, texts, attachment_names)
            self.status_bar.showMessage(_('Sending email to')+' '+to, 3000)

        if bad:
            bad = '\n'.join('<li>%s</li>'%(i,) for i in bad)
            d = warning_dialog(self, _('No suitable formats'),
                '<p>'+ _('Could not email the following books '
                'as no suitable formats were found:<br><ul>%s</ul>')%(bad,))
            d.exec_()

    def emails_sent(self, results, remove=[]):
        errors, good = [], []
        for jobname, exception, tb in results:
            id = jobname.partition(':')[0]
            title = jobname.partition(':')[-1]
            if exception is not None:
                errors.append([title, exception, tb])
            else:
                good.append(title)
        if errors:
            errors = '\n'.join([
                    '<li><b>%s</b><br>%s<br>%s<br></li>' %
                    (title, e, tb.replace('\n', '<br>')) for \
                            title, e, tb in errors
                    ])
            ConversionErrorDialog(self, _('Failed to email books'),
                    '<p>'+_('Failed to email the following books:')+\
                            '<ul>%s</ul>'%errors,
                        show=True)
        else:
            self.status_bar.showMessage(_('Sent by email:') + ', '.join(good),
                    5000)

    def cover_to_thumbnail(self, data):
        p = QPixmap()
        p.loadFromData(data)
        if not p.isNull():
            ht = self.device_manager.device_class.THUMBNAIL_HEIGHT \
                    if self.device_manager else Device.THUMBNAIL_HEIGHT
            p = p.scaledToHeight(ht, Qt.SmoothTransformation)
            return (p.width(), p.height(), pixmap_to_data(p))

    def email_news(self, id):
        opts = email_config().parse()
        accounts = [(account, [x.strip().lower() for x in x[0].split(',')])
                for account, x in opts.accounts.items() if x[1]]
        sent_mails = []
        for account, fmts in accounts:
            files = self.library_view.model().\
                    get_preferred_formats_from_ids([id], fmts)
            files = [f.name for f in files if f is not None]
            if not files:
                continue
            attachment = files[0]
            mi = self.library_view.model().db.get_metadata(id,
                    index_is_id=True)
            to_s = [account]
            subjects = [_('News:')+' '+mi.title]
            texts    = [_('Attached is the')+' '+mi.title]
            attachment_names = [mi.title+os.path.splitext(attachment)[1]]
            attachments = [attachment]
            jobnames = ['%s:%s'%(id, mi.title)]
            remove = [id] if config['delete_news_from_library_on_upload']\
                    else []
            self.emailer.send_mails(jobnames,
                    Dispatcher(partial(self.emails_sent, remove=remove)),
                    attachments, to_s, subjects, texts, attachment_names)
            sent_mails.append(to_s[0])
        if sent_mails:
            self.status_bar.showMessage(_('Sent news to')+' '+\
                    ', '.join(sent_mails),  3000)


    def sync_news(self):
        if self.device_connected:
            ids = list(dynamic.get('news_to_be_synced', set([])))
            ids = [id for id in ids if self.library_view.model().db.has_id(id)]
            files = self.library_view.model().get_preferred_formats_from_ids(
                                ids, self.device_manager.device_class.FORMATS)
            files = [f for f in files if f is not None]
            if not files:
                dynamic.set('news_to_be_synced', set([]))
                return
            metadata = self.library_view.model().get_metadata(ids,
                    rows_are_ids=True)
            names = []
            for mi in metadata:
                prefix = sanitize_file_name(mi['title'])
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                prefix = ascii_filename(prefix)
                names.append('%s_%d%s'%(prefix, id,
                    os.path.splitext(f.name)[1]))
                cdata = mi['cover']
                if cdata:
                    mi['cover'] = self.cover_to_thumbnail(cdata)
            dynamic.set('news_to_be_synced', set([]))
            if config['upload_news_to_device'] and files:
                remove = ids if \
                    config['delete_news_from_library_on_upload'] else []
                on_card = self.location_view.model().free[0] < \
                          self.location_view.model().free[1]
                self.upload_books(files, names, metadata,
                        on_card=on_card,
                        memory=[[f.name for f in files], remove])
                self.status_bar.showMessage(_('Sending news to device.'), 5000)


    def sync_to_device(self, on_card, delete_from_library,
            specific_format=None):
        rows = self.library_view.selectionModel().selectedRows()
        if not self.device_manager or not rows or len(rows) == 0:
            return
        ids = iter(self.library_view.model().id(r) for r in rows)
        metadata = self.library_view.model().get_metadata(rows)
        for mi in metadata:
            cdata = mi['cover']
            if cdata:
                mi['cover'] = self.cover_to_thumbnail(cdata)
        metadata = iter(metadata)
        _files   = self.library_view.model().get_preferred_formats(rows,
                                    self.device_manager.device_class.FORMATS,
                                    paths=True, set_metadata=True,
                                    specific_format=specific_format)
        files = [getattr(f, 'name', None) for f in _files]
        bad, good, gf, names, remove_ids = [], [], [], [], []
        for f in files:
            mi = metadata.next()
            id = ids.next()
            if f is None:
                bad.append(mi['title'])
            else:
                remove_ids.append(id)
                good.append(mi)
                gf.append(f)
                t = mi['title']
                if not t:
                    t = _('Unknown')
                a = mi['authors']
                if not a:
                    a = _('Unknown')
                prefix = sanitize_file_name(t+' - '+a)
                if not isinstance(prefix, unicode):
                    prefix = prefix.decode(preferred_encoding, 'replace')
                prefix = ascii_filename(prefix)
                names.append('%s_%d%s'%(prefix, id, os.path.splitext(f)[1]))
        remove = remove_ids if delete_from_library else []
        self.upload_books(gf, names, good, on_card, memory=(_files, remove))
        self.status_bar.showMessage(_('Sending books to device.'), 5000)
        if bad:
            bad = '\n'.join('<li>%s</li>'%(i,) for i in bad)
            d = warning_dialog(self, _('No suitable formats'),
                    _('Could not upload the following books to the device, '
                'as no suitable formats were found:<br><ul>%s</ul>')%(bad,))
            d.exec_()

    def upload_booklists(self):
        '''
        Upload metadata to device.
        '''
        self.device_manager.sync_booklists(Dispatcher(self.metadata_synced),
                                           self.booklists())

    def metadata_synced(self, job):
        '''
        Called once metadata has been uploaded.
        '''
        if job.exception is not None:
            self.device_job_exception(job)
            return
        cp, fs = job.result
        self.location_view.model().update_devices(cp, fs)

    def upload_books(self, files, names, metadata, on_card=False, memory=None):
        '''
        Upload books to device.
        :param files: List of either paths to files or file like objects
        '''
        titles = [i['title'] for i in metadata]
        job = self.device_manager.upload_books(
                Dispatcher(self.books_uploaded),
                files, names, on_card=on_card,
                metadata=metadata, titles=titles
              )
        self.upload_memory[job] = (metadata, on_card, memory, files)

    def books_uploaded(self, job):
        '''
        Called once books have been uploaded.
        '''
        metadata, on_card, memory, files = self.upload_memory.pop(job)

        if job.exception is not None:
            if isinstance(job.exception, FreeSpaceError):
                where = 'in main memory.' if 'memory' in str(job.exception) \
                        else 'on the storage card.'
                titles = '\n'.join(['<li>'+mi['title']+'</li>' \
                                    for mi in metadata])
                d = error_dialog(self, _('No space on device'),
                                 _('<p>Cannot upload books to device there '
                                 'is no more free space available ')+where+
                                 '</p>\n<ul>%s</ul>'%(titles,))
                d.exec_()
            else:
                self.device_job_exception(job)
            return

        self.device_manager.add_books_to_metadata(job.result,
                metadata, self.booklists())

        self.upload_booklists()

        view = self.card_view if on_card else self.memory_view
        view.model().resort(reset=False)
        view.model().research()
        for f in files:
            getattr(f, 'close', lambda : True)()
        if memory and memory[1]:
            self.library_view.model().delete_books_by_id(memory[1])


