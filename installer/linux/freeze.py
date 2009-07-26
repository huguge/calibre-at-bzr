#!/usr/bin/env  python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Create linux binary.
'''

def freeze():
    import glob, sys, tarfile, os, textwrap, shutil
    from contextlib import closing
    from cx_Freeze import Executable, setup
    from calibre.constants import __version__, __appname__
    from calibre.linux import entry_points
    from calibre import walk
    from calibre.web.feeds.recipes import recipe_modules
    from calibre.ebooks.lrf.fonts import FONT_MAP
    import calibre


    QTDIR          = '/usr/lib/qt4'
    QTDLLS         = ('QtCore', 'QtGui', 'QtNetwork', 'QtSvg', 'QtXml',
            'QtWebKit', 'QtDBus')

    binary_excludes = ['libGLcore*', 'libGL*', 'libnvidia*']

    binary_includes = [
                       '/usr/bin/pdftohtml',
                       '/usr/lib/libunrar.so',
                       '/usr/lib/libsqlite3.so.0',
                       '/usr/lib/libsqlite3.so.0',
                       '/usr/lib/libmng.so.1',
                       '/usr/lib/libpodofo.so.0.6.99',
                       '/lib/libz.so.1',
                       '/lib/libbz2.so.1',
                       '/usr/lib/libpoppler.so.4',
                       '/usr/lib/libxml2.so.2',
                       '/usr/lib/libdbus-1.so.3',
                       '/usr/lib/libopenjpeg.so.2',
                       '/usr/lib/libxslt.so.1',
                       '/usr/lib/libxslt.so.1',
                       '/usr/lib/libgthread-2.0.so.0',
                       '/usr/lib/gcc/i686-pc-linux-gnu/4.3.3/libstdc++.so.6',
                       '/usr/lib/libpng12.so.0',
                       '/usr/lib/libexslt.so.0',
                       '/usr/lib/libMagickWand.so',
                       '/usr/lib/libMagickCore.so',
                       '/usr/lib/libgcrypt.so.11',
                       '/usr/lib/libgpg-error.so.0',
                       '/usr/lib/libphonon.so.4',
                       ]

    binary_includes += [os.path.join(QTDIR, 'lib%s.so.4'%x) for x in QTDLLS]


    d = os.path.dirname
    CALIBRESRC = d(d(d(os.path.abspath(calibre.__file__))))
    CALIBREPLUGINS = os.path.join(CALIBRESRC, 'src', 'calibre', 'plugins')
    FREEZE_DIR = os.path.join(CALIBRESRC, 'build', 'cx_freeze')
    DIST_DIR   = os.path.join(CALIBRESRC, 'dist')

    os.chdir(CALIBRESRC)

    print 'Freezing calibre located at', CALIBRESRC

    sys.path.insert(0, os.path.join(CALIBRESRC, 'src'))

    entry_points = entry_points['console_scripts'] + entry_points['gui_scripts']
    entry_points = ['calibre_postinstall=calibre.linux:binary_install',
                    'calibre-parallel=calibre.parallel:main'] + entry_points
    executables = {}
    for ep in entry_points:
        executables[ep.split('=')[0].strip()] = (ep.split('=')[1].split(':')[0].strip(),
                                                 ep.split(':')[-1].strip())

    if os.path.exists(FREEZE_DIR):
        shutil.rmtree(FREEZE_DIR)
    os.makedirs(FREEZE_DIR)

    if not os.path.exists(DIST_DIR):
        os.makedirs(DIST_DIR)

    includes = [x[0] for x in executables.values()]
    includes += ['calibre.ebooks.lrf.fonts.prs500.'+x for x in FONT_MAP.values()]
    includes += ['email.iterators', 'email.generator']


    excludes = ['matplotlib', "Tkconstants", "Tkinter", "tcl", "_imagingtk",
                "ImageTk", "FixTk", 'wx', 'PyQt4.QtAssistant', 'PyQt4.QtOpenGL.so',
                'PyQt4.QtScript.so', 'PyQt4.QtSql.so', 'PyQt4.QtTest.so', 'qt',
                'glib', 'gobject']

    packages = ['calibre', 'encodings', 'cherrypy', 'cssutils', 'xdg',
                'dateutil', 'dns', 'email']

    includes += ['calibre.web.feeds.recipes.'+r for r in recipe_modules]
    includes += ['calibre.gui2.convert.'+x.split('/')[-1].rpartition('.')[0] for x in \
            glob.glob('src/calibre/gui2/convert/*.py')]

    LOADER = '/tmp/loader.py'
    open(LOADER, 'wb').write('# This script is never actually used.\nimport sys')

    INIT_SCRIPT = '/tmp/init.py'
    open(INIT_SCRIPT, 'wb').write(textwrap.dedent('''
    ## Load calibre module specified in the environment variable CALIBRE_CX_EXE
    ## Also restrict sys.path to the executables' directory and add the
    ## executables directory to LD_LIBRARY_PATH
    import encodings
    import os
    import sys
    import warnings
    import zipimport
    import locale
    import codecs

    enc = locale.getdefaultlocale()[1]
    if not enc:
        enc = locale.nl_langinfo(locale.CODESET)
    enc = codecs.lookup(enc if enc else 'UTF-8').name
    sys.setdefaultencoding(enc)

    paths = os.environ.get('LD_LIBRARY_PATH', '').split(os.pathsep)
    if DIR_NAME not in paths or not sys.getfilesystemencoding():
        paths.insert(0, DIR_NAME)
        os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(paths)
        os.environ['PYTHONIOENCODING'] = enc
        os.execv(sys.executable, sys.argv)

    sys.path = sys.path[:3]
    sys.frozen = True
    sys.frozen_path = DIR_NAME

    executables = %(executables)s

    exe = os.environ.get('CALIBRE_CX_EXE', False)
    ret = 1
    if not exe:
        print >>sys.stderr, 'Invalid invocation of calibre loader. CALIBRE_CX_EXE not set'
    elif exe not in executables:
        print >>sys.stderr, 'Invalid invocation of calibre loader. CALIBRE_CX_EXE=%%s is unknown'%%exe
    else:
        from PyQt4.QtCore import QCoreApplication
        QCoreApplication.setLibraryPaths([sys.frozen_path, os.path.join(sys.frozen_path, "qtplugins")])
        sys.argv[0] = exe
        module, func = executables[exe]
        module = __import__(module, fromlist=[1])
        func = getattr(module, func)
        ret = func()

    module = sys.modules.get("threading")
    if module is not None:
        module._shutdown()
    sys.exit(ret)
    ''')%dict(executables=repr(executables)))
    sys.argv = ['freeze', 'build_exe']
    setup(
          name        = __appname__,
          version     = __version__,
          executables = [Executable(script=LOADER, targetName='loader', compress=False)],
          options     = { 'build_exe' :
                         {
                          'build_exe'       : os.path.join(CALIBRESRC, 'build/cx_freeze'),
                          'optimize'        : 2,
                          'excludes'        : excludes,
                          'includes'        : includes,
                          'packages'        : packages,
                          'init_script'     : INIT_SCRIPT,
                          'copy_dependent_files' : True,
                          'create_shared_zip'    : False,
                          }
                         }
          )

    def copy_binary(src, dest_dir):
        dest = os.path.join(dest_dir, os.path.basename(src))
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        shutil.copyfile(os.path.realpath(src), dest)
        shutil.copymode(os.path.realpath(src), dest)

    for f in binary_includes:
        copy_binary(f, FREEZE_DIR)

    for pat in binary_excludes:
        matches = glob.glob(os.path.join(FREEZE_DIR, pat))
        for f in matches:
            os.remove(f)

    print 'Adding calibre plugins...'
    os.makedirs(os.path.join(FREEZE_DIR, 'plugins'))
    for f in glob.glob(os.path.join(CALIBREPLUGINS, '*.so')):
        copy_binary(f, os.path.join(FREEZE_DIR, 'plugins'))

    print 'Adding Qt plugins...'
    plugdir = os.path.join(QTDIR, 'plugins')
    for dirpath, dirnames, filenames in os.walk(plugdir):
        for f in filenames:
            if not f.endswith('.so') or 'designer' in dirpath or 'codecs' in dirpath or 'sqldrivers' in dirpath:
                continue
            f = os.path.join(dirpath, f)
            dest_dir = dirpath.replace(plugdir, os.path.join(FREEZE_DIR, 'qtplugins'))
            copy_binary(f, dest_dir)

    print 'Creating launchers'
    for exe in executables:
        path = os.path.join(FREEZE_DIR, exe)
        open(path, 'wb').write(textwrap.dedent('''\
        #!/bin/sh
        export CALIBRE_CX_EXE=%s
        path=`readlink -e $0`
        base=`dirname $path`
        loader=$base/loader
        export LD_LIBRARY_PATH=$base:$LD_LIBRARY_PATH
        $loader "$@"
        ''')%exe)
        os.chmod(path, 0755)

    exes = list(executables.keys())
    exes.remove('calibre_postinstall')
    exes.remove('calibre-parallel')
    open(os.path.join(FREEZE_DIR, 'manifest'), 'wb').write('\n'.join(exes))

    print 'Creating archive...'
    dist = open(os.path.join(DIST_DIR, 'calibre-%s-i686.tar.bz2'%__version__), 'wb')
    with closing(tarfile.open(fileobj=dist, mode='w:bz2',
                              format=tarfile.PAX_FORMAT)) as tf:
        for f in walk(FREEZE_DIR):
            name = f.replace(FREEZE_DIR, '')[1:]
            if name:
                tf.add(f, name)
    dist.flush()
    dist.seek(0, 2)
    print 'Archive %s created: %.2f MB'%(dist.name, dist.tell()/(1024.**2))
    return 0

if __name__ == '__main__':
    freeze()
