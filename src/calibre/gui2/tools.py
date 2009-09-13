#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Logic for setting up conversion jobs
'''

import cPickle

from PyQt4.Qt import QDialog, QProgressDialog, QString, QTimer, SIGNAL

from calibre.ptempfile import PersistentTemporaryFile
from calibre.gui2 import warning_dialog, question_dialog
from calibre.gui2.convert.single import NoSupportedInputFormats
from calibre.gui2.convert.single import Config as SingleConfig, \
    get_input_format_for_book
from calibre.gui2.convert.bulk import BulkConfig
from calibre.gui2.convert.metadata import create_opf_file, create_cover_file
from calibre.customize.conversion import OptionRecommendation
from calibre.utils.config import prefs
from calibre.ebooks.conversion.config import GuiRecommendations, \
    load_defaults, load_specifics, save_specifics

def convert_single_ebook(parent, db, book_ids, auto_conversion=False, out_format=None):
    changed = False
    jobs = []
    bad = []

    total = len(book_ids)
    if total == 0:
        return None, None, None
    parent.status_bar.showMessage(_('Starting conversion of %d books') % total, 2000)

    for i, book_id in enumerate(book_ids):
        temp_files = []

        try:
            d = SingleConfig(parent, db, book_id, None, out_format)

            if auto_conversion:
                d.accept()
                result = QDialog.Accepted
            else:
                result = d.exec_()

            if result == QDialog.Accepted:
                #if not convert_existing(parent, db, [book_id], d.output_format):
                #    continue

                mi = db.get_metadata(book_id, True)
                in_file = db.format_abspath(book_id, d.input_format, True)

                out_file = PersistentTemporaryFile('.' + d.output_format)
                out_file.write(d.output_format)
                out_file.close()
                temp_files = []

                try:
                    dtitle = unicode(mi.title)
                except:
                    dtitle = repr(mi.title)
                desc = _('Convert book %d of %d (%s)') % (i + 1, total, dtitle)

                recs = cPickle.loads(d.recommendations)
                if d.opf_file is not None:
                    recs.append(('read_metadata_from_opf', d.opf_file.name,
                        OptionRecommendation.HIGH))
                    temp_files.append(d.opf_file)
                if d.cover_file is not None:
                    recs.append(('cover', d.cover_file.name,
                        OptionRecommendation.HIGH))
                    temp_files.append(d.cover_file)
                args = [in_file, out_file.name, recs]
                temp_files.append(out_file)
                jobs.append(('gui_convert', args, desc, d.output_format.upper(), book_id, temp_files))

                changed = True
        except NoSupportedInputFormats:
            bad.append(book_id)

    if bad != []:
        res = []
        for id in bad:
            title = db.title(id, True)
            res.append('%s'%title)

        msg = '%s' % '\n'.join(res)
        warning_dialog(parent, _('Could not convert some books'),
            _('Could not convert %d of %d books, because no suitable source'
               ' format was found.') % (len(res), total),
            msg).exec_()

    return jobs, changed, bad

def convert_bulk_ebook(parent, queue, db, book_ids, out_format=None, args=[]):
    changed = False
    jobs = []
    bad = []

    total = len(book_ids)
    if total == 0:
        return None, None, None
    parent.status_bar.showMessage(_('Starting conversion of %d books') % total, 2000)

    d = BulkConfig(parent, db, out_format)
    if d.exec_() != QDialog.Accepted:
        return jobs, changed, bad

    output_format = d.output_format
    user_recs = cPickle.loads(d.recommendations)

    book_ids = convert_existing(parent, db, book_ids, output_format)
    return QueueBulk(parent, book_ids, output_format, queue, db, user_recs, args)

class QueueBulk(QProgressDialog):

    def __init__(self, parent, book_ids, output_format, queue, db, user_recs, args):
        QProgressDialog.__init__(self, '',
                QString(), 0, len(book_ids), parent)
        self.setWindowTitle(_('Queueing books for bulk conversion'))
        self.book_ids, self.output_format, self.queue, self.db, self.args, self.user_recs = \
                book_ids, output_format, queue, db, args, user_recs
        self.parent = parent
        self.i, self.bad, self.jobs, self.changed = 0, [], [], False
        self.timer = QTimer(self)
        self.connect(self.timer, SIGNAL('timeout()'), self.do_book)
        self.timer.start()
        self.exec_()

    def do_book(self):
        if self.i >= len(self.book_ids):
            self.timer.stop()
            return self.do_queue()
        book_id = self.book_ids[self.i]
        self.i += 1

        temp_files = []

        try:
            input_format = get_input_format_for_book(self.db, book_id, None)[0]
            mi, opf_file = create_opf_file(self.db, book_id)
            in_file = self.db.format_abspath(book_id, input_format, True)

            out_file = PersistentTemporaryFile('.' + self.output_format)
            out_file.write(self.output_format)
            out_file.close()
            temp_files = []

            combined_recs = GuiRecommendations()
            default_recs = load_defaults('%s_input' % input_format)
            specific_recs = load_specifics(self.db, book_id)
            for key in default_recs:
                combined_recs[key] = default_recs[key]
            for key in specific_recs:
                combined_recs[key] = specific_recs[key]
            for item in self.user_recs:
                combined_recs[item[0]] = item[1]
            save_specifics(self.db, book_id, combined_recs)
            lrecs = list(combined_recs.to_recommendations())

            cover_file = create_cover_file(self.db, book_id)

            if opf_file is not None:
                lrecs.append(('read_metadata_from_opf', opf_file.name,
                    OptionRecommendation.HIGH))
                temp_files.append(opf_file)
            if cover_file is not None:
                lrecs.append(('cover', cover_file.name,
                    OptionRecommendation.HIGH))
                temp_files.append(cover_file)

            for x in list(lrecs):
                if x[0] == 'debug_pipeline':
                    lrecs.remove(x)

            try:
                dtitle = unicode(mi.title)
            except:
                dtitle = repr(mi.title)
            self.setLabelText(_('Queueing ')+dtitle)
            desc = _('Convert book %d of %d (%s)') % (self.i, len(self.book_ids), dtitle)

            args = [in_file, out_file.name, lrecs]
            temp_files.append(out_file)
            self.jobs.append(('gui_convert', args, desc, self.output_format.upper(), book_id, temp_files))

            self.changed = True
            self.setValue(self.i)
        except NoSupportedInputFormats:
            self.bad.append(book_id)

    def do_queue(self):
        self.hide()
        if self.bad != []:
            res = []
            for id in self.bad:
                title = self.db.title(id, True)
                res.append('%s'%title)

            msg = '%s' % '\n'.join(res)
            warning_dialog(self.parent, _('Could not convert some books'),
                _('Could not convert %d of %d books, because no suitable '
                'source format was found.') % (len(res), len(self.book_ids)),
                msg).exec_()
        self.parent = None
        self.jobs.reverse()
        self.queue(self.jobs, self.changed, self.bad, *self.args)

def fetch_scheduled_recipe(recipe, script):
    from calibre.gui2.dialogs.scheduler import config
    from calibre.ebooks.conversion.config import load_defaults
    fmt = prefs['output_format'].lower()
    pt = PersistentTemporaryFile(suffix='_recipe_out.%s'%fmt.lower())
    pt.close()
    recs = []
    ps = load_defaults('page_setup')
    if 'output_profile' in ps:
        recs.append(('output_profile', ps['output_profile'],
            OptionRecommendation.HIGH))
    lf = load_defaults('look_and_feel')
    if lf.get('base_font_size', 0.0) != 0.0:
        recs.append(('base_font_size', lf['base_font_size'],
            OptionRecommendation.HIGH))

    lr = load_defaults('lrf_output')
    if lr.get('header', False):
        recs.append(('header', True, OptionRecommendation.HIGH))
        recs.append(('header_format', '%t', OptionRecommendation.HIGH))

    args = [script, pt.name, recs]
    if recipe.needs_subscription:
        x = config.get('recipe_account_info_%s'%recipe.id, False)
        if not x:
            raise ValueError(_('You must set a username and password for %s')%recipe.title)
        recs.append(('username', x[0], OptionRecommendation.HIGH))
        recs.append(('password', x[1], OptionRecommendation.HIGH))


    return 'gui_convert', args, _('Fetch news from ')+recipe.title, fmt.upper(), [pt]

def convert_existing(parent, db, book_ids, output_format):
    already_converted_ids = []
    already_converted_titles = []
    for book_id in book_ids:
        if db.has_format(book_id, output_format, index_is_id=True):
            already_converted_ids.append(book_id)
            already_converted_titles.append(db.get_metadata(book_id, True).title)

    if already_converted_ids:
        if not question_dialog(parent, _('Convert existing'),
                _('The following books have already been converted to %s format. '
                   'Do you wish to reconvert them?') % output_format,
                '\n'.join(already_converted_titles)):
            book_ids = [x for x in book_ids if x not in already_converted_ids]

    return book_ids
