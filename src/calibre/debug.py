#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Embedded console for debugging.
'''

import sys, os
from calibre.utils.config import OptionParser
from calibre.constants import iswindows
from calibre import prints

def option_parser():
    parser = OptionParser(usage='''\
%prog [options]

Run an embedded python interpreter.
''')
    parser.add_option('-c', '--command', help='Run python code.', default=None)
    parser.add_option('-e', '--exec-file', default=None, help='Run the python code in file.')
    parser.add_option('-d', '--debug-device-driver', default=False, action='store_true',
                      help='Debug the specified device driver.')
    parser.add_option('-g', '--gui',  default=False, action='store_true',
                      help='Run the GUI',)
    parser.add_option('-w', '--viewer',  default=False, action='store_true',
                      help='Run the ebook viewer',)
    parser.add_option('--paths', default=False, action='store_true',
            help='Output the paths necessary to setup the calibre environment')
    parser.add_option('--migrate', action='store_true', default=False,
                      help='Migrate old database. Needs two arguments. Path '
                           'to library1.db and path to new library folder.')
    parser.add_option('--add-simple-plugin', default=None,
            help='Add a simple plugin (i.e. a plugin that consists of only a '
            '.py file), by specifying the path to the py file containing the '
            'plugin code.')
    parser.add_option('--reinitialize-db', default=None,
            help='Re-initialize the sqlite calibre database at the '
            'specified path. Useful to recover from db corruption.')

    return parser

def reinit_db(dbpath, callback=None):
    if not os.path.exists(dbpath):
        raise ValueError(dbpath + ' does not exist')
    from calibre.library.sqlite import connect
    from contextlib import closing
    import shutil
    conn = connect(dbpath, False)
    uv = conn.get('PRAGMA user_version;', all=False)
    conn.execute('PRAGMA writable_schema=ON')
    conn.commit()
    sql_lines = conn.dump()
    conn.close()
    dest = dbpath + '.tmp'
    try:
        with closing(connect(dest, False)) as nconn:
            nconn.execute('create temporary table temp_sequence(id INTEGER PRIMARY KEY AUTOINCREMENT)')
            nconn.commit()
            if callable(callback):
                callback(len(sql_lines), True)
            for i, line in enumerate(sql_lines):
                try:
                    nconn.execute(line)
                except:
                    import traceback
                    prints('SQL line %r failed with error:'%line)
                    prints(traceback.format_exc())
                    continue
                finally:
                    if callable(callback):
                        callback(i, False)
            nconn.execute('pragma user_version=%d'%int(uv))
            nconn.commit()
        os.remove(dbpath)
        shutil.copyfile(dest, dbpath)
    finally:
        if os.path.exists(dest):
            os.remove(dest)
    prints('Database successfully re-initialized')

def migrate(old, new):
    from calibre.utils.config import prefs
    from calibre.library.database import LibraryDatabase
    from calibre.library.database2 import LibraryDatabase2
    from calibre.utils.terminfo import ProgressBar
    from calibre import terminal_controller
    class Dummy(ProgressBar):
        def setLabelText(self, x): pass
        def setAutoReset(self, y): pass
        def reset(self): pass
        def setRange(self, min, max):
            self.min = min
            self.max = max
        def setValue(self, val):
            self.update(float(val)/getattr(self, 'max', 1))

    db = LibraryDatabase(old)
    db2 = LibraryDatabase2(new)
    db2.migrate_old(db, Dummy(terminal_controller, 'Migrating database...'))
    prefs['library_path'] = os.path.abspath(new)
    print 'Database migrated to', os.path.abspath(new)

def debug_device_driver():
    from calibre.devices import debug
    debug(ioreg_to_tmp=True, buf=sys.stdout)
    if iswindows:
        raw_input('Press Enter to continue...')


def add_simple_plugin(path_to_plugin):
    import tempfile, zipfile, shutil
    tdir = tempfile.mkdtemp()
    open(os.path.join(tdir, 'custom_plugin.py'),
            'wb').write(open(path_to_plugin, 'rb').read())
    odir = os.getcwd()
    os.chdir(tdir)
    zf = zipfile.ZipFile('plugin.zip', 'w')
    zf.write('custom_plugin.py')
    zf.close()
    from calibre.customize.ui import main
    main(['calibre-customize', '-a', 'plugin.zip'])
    os.chdir(odir)
    shutil.rmtree(tdir)



def main(args=sys.argv):
    from calibre.constants import debug
    debug()
    if len(args) > 2 and args[1] in ('-e', '--exec-file'):
        sys.argv = [args[2]] + args[3:]
        ef = os.path.abspath(args[2])
        base = os.path.dirname(ef)
        sys.path.insert(0, base)
        g = globals()
        g['__name__'] = '__main__'
        execfile(ef, g)
        return

    opts, args = option_parser().parse_args(args)
    if opts.gui:
        from calibre.gui2.main import main
        main(['calibre'])
    elif opts.viewer:
        from calibre.gui2.viewer.main import main
        vargs = ['ebook-viewer', '--debug-javascript']
        if len(args) > 1:
            vargs.append(args[-1])
        main(vargs)
    elif opts.command:
        sys.argv = args[:1]
        exec opts.command
    elif opts.debug_device_driver:
        debug_device_driver()
    elif opts.migrate:
        if len(args) < 3:
            print 'You must specify the path to library1.db and the path to the new library folder'
            return 1
        migrate(args[1], args[2])
    elif opts.add_simple_plugin is not None:
        add_simple_plugin(opts.add_simple_plugin)
    elif opts.paths:
        prints('CALIBRE_RESOURCES_PATH='+sys.resources_location)
        prints('CALIBRE_EXTENSIONS_PATH='+sys.extensions_location)
        prints('CALIBRE_PYTHON_PATH='+os.pathsep.join(sys.path))
    elif opts.reinitialize_db is not None:
        reinit_db(opts.reinitialize_db)
    else:
        from calibre import ipython
        ipython()

    return 0

if __name__ == '__main__':
    sys.exit(main())
