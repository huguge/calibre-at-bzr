#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, shutil, platform, subprocess, stat, py_compile, glob

from setup import Command, modules, basenames, functions

is64bit = platform.architecture()[0] == '64bit'
arch = 'x86_64' if is64bit else 'i686'
ffi = '/usr/lib/libffi.so.5' if is64bit else '/usr/lib/gcc/i686-pc-linux-gnu/4.4.1/libffi.so.4'


QTDIR          = '/usr/lib/qt4'
QTDLLS         = ('QtCore', 'QtGui', 'QtNetwork', 'QtSvg', 'QtXml', 'QtWebKit', 'QtDBus')


binary_includes = [
                '/usr/bin/pdftohtml',
                '/usr/lib/libwmflite-0.2.so.7',
                '/usr/lib/liblcms.so.1',
                '/usr/lib/libunrar.so',
                '/usr/lib/libsqlite3.so.0',
                '/usr/lib/libsqlite3.so.0',
                '/usr/lib/libmng.so.1',
                '/usr/lib/libpodofo.so.0.6.99',
                '/lib/libz.so.1',
                '/usr/lib/libtiff.so.3',
                '/lib/libbz2.so.1',
                '/usr/lib/libpoppler.so.5',
                '/usr/lib/libxml2.so.2',
                '/usr/lib/libopenjpeg.so.2',
                '/usr/lib/libxslt.so.1',
                '/usr/lib/libjpeg.so.7',
                '/usr/lib/libxslt.so.1',
                '/usr/lib/libgthread-2.0.so.0',
                '/usr/lib/gcc/***-pc-linux-gnu/4.4.1/libstdc++.so.6'.replace('***',
                    arch),
                ffi,
                '/usr/lib/libpng12.so.0',
                '/usr/lib/libexslt.so.0',
                '/usr/lib/libMagickWand.so.2',
                '/usr/lib/libMagickCore.so.2',
                '/usr/lib/libgcrypt.so.11',
                '/usr/lib/libgpg-error.so.0',
                '/usr/lib/libphonon.so.4',
                '/usr/lib/libssl.so.0.9.8',
                '/usr/lib/libcrypto.so.0.9.8',
                '/lib/libreadline.so.6',
                ]
binary_includes += [os.path.join(QTDIR, 'lib%s.so.4'%x) for x in QTDLLS]

SITE_PACKAGES = ['IPython', 'PIL', 'dateutil', 'dns', 'PyQt4', 'mechanize',
        'sip.so', 'BeautifulSoup.py', 'ClientForm.py', 'lxml']

class LinuxFreeze2(Command):

    def run(self, opts):
        self.drop_privileges()
        self.opts = opts
        self.src_root = self.d(self.SRC)
        self.base = self.j(self.src_root, 'build', 'linfrozen')
        self.py_ver = '.'.join(map(str, sys.version_info[:2]))
        self.lib_dir = self.j(self.base, 'lib')
        self.bin_dir = self.j(self.base, 'bin')

        #self.initbase()
        #self.copy_libs()
        #self.copy_python()
        #self.compile_mount_helper()
        self.build_launchers()

    def initbase(self):
        if os.path.exists(self.base):
            shutil.rmtree(self.base)
        os.makedirs(self.base)

    def copy_libs(self):
        self.info('Copying libs...')
        os.mkdir(self.lib_dir)
        os.mkdir(self.bin_dir)
        for x in binary_includes:
            dest = self.bin_dir if '/bin/' in x else self.lib_dir
            shutil.copy2(x, dest)
        shutil.copy2('/usr/lib/libpython%s.so.1.0'%self.py_ver, dest)

        base = self.j(QTDIR, 'plugins')
        dest = self.j(self.lib_dir, 'qt_plugins')
        os.mkdir(dest)
        for x in os.listdir(base):
            y = self.j(base, x)
            if x not in ('designer', 'sqldrivers', 'codecs'):
                shutil.copytree(y, self.j(dest, x))

        im = glob.glob('/usr/lib/ImageMagick-*')[0]
        dest = self.j(self.lib_dir, 'ImageMagick')
        shutil.copytree(im, dest, ignore=shutil.ignore_patterns('*.a'))

    def compile_mount_helper(self):
        self.info('Compiling mount helper...')
        self.regain_privileges()
        dest = self.j(self.bin_dir, 'calibre-mount-helper')
        subprocess.check_call(['gcc', '-Wall', '-pedantic',
            self.j(self.SRC, 'calibre', 'devices',
                'linux_mount_helper.c'), '-o', dest])
        os.chown(dest, 0, 0)
        os.chmod(dest, stat.S_ISUID|stat.S_ISGID|stat.S_IRUSR|stat.S_IWUSR|\
                stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH)
        self.drop_privileges()

    def copy_python(self):
        self.info('Copying python...')

        def ignore_in_lib(base, items):
            ans = []
            for x in items:
                x = os.path.join(base, x)
                if (os.path.isfile(x) and os.path.splitext(x)[1] in ('.so',
                        '.py')) or \
                   (os.path.isdir(x) and x in ('.svn', '.bzr', 'test')):
                    continue
                ans.append(x)
            return ans

        srcdir = self.j('/usr/lib/python'+self.py_ver)
        self.py_dir = self.j(self.lib_dir, self.b(srcdir))
        os.mkdir(self.py_dir)

        for x in os.listdir(srcdir):
            y = self.j(srcdir, x)
            ext = os.path.splitext(x)[1]
            if os.path.isdir(y) and x not in ('test', 'hotshot', 'distutils',
                    'site-packages',  'idlelib', 'test', 'lib2to3'):
                shutil.copytree(y, self.j(self.py_dir, x),
                        ignore=ignore_in_lib)
            if os.path.isfile(y) and ext in ('.py', '.so'):
                shutil.copy2(y, self.py_dir)

        srcdir = self.j(srcdir, 'site-packages')
        dest = self.j(self.py_dir, 'site-packages')
        os.mkdir(dest)
        for x in SITE_PACKAGES:
            x = self.j(srcdir, x)
            ext = os.path.splitext(x)[1]
            if os.path.isdir(x):
                shutil.copytree(x, self.j(dest, self.b(x)),
                        ignore=ignore_in_lib)
            if os.path.isfile(x) and ext in ('.py', '.so'):
                shutil.copy2(x, dest)

        for x in os.listdir(self.SRC):
            shutil.copytree(self.j(self.SRC, x), self.j(dest, x),
                    ignore=ignore_in_lib)
        for x in ('translations', 'manual'):
            x = self.j(dest, 'calibre', x)
            shutil.rmtree(x)

        shutil.copytree(self.j(self.src_root, 'resources'), self.j(self.base,
                'resources'))

        for x in os.walk(self.py_dir):
            for f in x[-1]:
                if f.endswith('.py'):
                    y = self.j(x[0], f)
                    rel = os.path.relpath(y, self.py_dir)
                    try:
                        py_compile.compile(y, dfile=rel, doraise=True)
                        os.remove(y)
                        z = y+'c'
                        if os.path.exists(z):
                            os.remove(z)
                    except:
                        self.warn('Failed to byte-compile', y)

    def run_builder(self, cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        self.info(*cmd)
        self.info(p.stdout.read())
        self.info(p.stderr.read())

        if p.wait() != 0:
            self.info('Failed to run builder')
            sys.exit(1)

    def build_launchers(self):
        self.obj_dir = self.j(self.src_root, 'build', 'launcher')
        if not os.path.exists(self.obj_dir):
            os.makedirs(self.obj_dir)
        base = self.j(self.src_root, 'setup', 'installer', 'linux')
        sources = [self.j(base, x) for x in ['util.c']]
        headers = [self.j(base, x) for x in ['util.h']]
        objects = [self.j(self.obj_dir, self.b(x)+'.o') for x in sources]
        cflags  = '-W -Wall -c -O2 -pipe -DPYTHON_VER="python%s"'%self.py_ver
        cflags  = cflags.split() + ['-I/usr/include/python'+self.py_ver]
        for src, obj in zip(sources, objects):
            if not self.newer(obj, headers+[src, __file__]): continue
            cmd = ['gcc'] + cflags + ['-fPIC', '-o', obj, src]
            self.run_builder(cmd)

        dll = self.j(self.lib_dir, 'libcalibre-launcher.so')
        if self.newer(dll, objects):
            cmd = ['gcc', '-O2', '-Wl,--rpath=$ORIGIN/../lib', '-fPIC', '-o', dll, '-shared'] + objects + \
                    ['-lpython'+self.py_ver]
            self.info('Linking libcalibre-launcher.so')
            self.run_builder(cmd)

        src = self.j(base, 'main.c')
        for typ in ('console', 'gui', ):
            self.info('Processing %s launchers'%typ)
            for mod, bname, func in zip(modules[typ], basenames[typ],
                    functions[typ]):
                xflags = list(cflags)
                xflags += ['-DGUI_APP='+('1' if type == 'gui' else '0')]
                xflags += ['-DMODULE="%s"'%mod, '-DBASENAME="%s"'%bname,
                    '-DFUNCTION="%s"'%func]

                dest = self.j(self.obj_dir, bname+'.o')
                if self.newer(dest, [src, __file__]+headers):
                    self.info('Compiling', bname)
                    cmd = ['gcc'] + xflags + [src, '-o', dest]
                    self.run_builder(cmd)
                exe = self.j(self.bin_dir, bname)
                if self.newer(exe, [dest, __file__]):
                    self.info('Linking', bname)
                    cmd = ['gcc', '-O2', '-Wl,--rpath=$ORIGIN/../lib',
                            '-o', exe,
                            dest,
                            '-L'+self.lib_dir,
                            '-lcalibre-launcher',
                            ]

                    self.run_builder(cmd)






