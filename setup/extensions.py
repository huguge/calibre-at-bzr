#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, os, shlex, subprocess, glob, shutil
from distutils import sysconfig

from PyQt4.pyqtconfig import QtGuiModuleMakefile

from setup import Command, islinux, isbsd, isosx, SRC, iswindows
from setup.build_environment import (fc_inc, fc_lib, chmlib_inc_dirs,
        fc_error, poppler_libs, poppler_lib_dirs, poppler_inc_dirs, podofo_inc,
        podofo_lib, podofo_error, poppler_error, pyqt, OSX_SDK, NMAKE,
        QMAKE, msvc, MT, win_inc, win_lib, png_inc_dirs, win_ddk,
        magick_inc_dirs, magick_lib_dirs, png_lib_dirs, png_libs,
        magick_error, magick_libs, ft_lib_dirs, ft_libs, jpg_libs,
        jpg_lib_dirs, chmlib_lib_dirs, sqlite_inc_dirs, icu_inc_dirs,
        icu_lib_dirs, poppler_cflags)
MT
isunix = islinux or isosx or isbsd

make = 'make' if isunix else NMAKE

class Extension(object):

    def absolutize(self, paths):
        return list(set([x if os.path.isabs(x) else os.path.join(SRC, x.replace('/',
            os.sep)) for x in paths]))


    def __init__(self, name, sources, **kwargs):
        self.name = name
        self.needs_cxx = bool([1 for x in sources if os.path.splitext(x)[1] in
            ('.cpp', '.c++', '.cxx')])
        self.sources = self.absolutize(sources)
        self.headers = self.absolutize(kwargs.get('headers', []))
        self.sip_files = self.absolutize(kwargs.get('sip_files', []))
        self.inc_dirs = self.absolutize(kwargs.get('inc_dirs', []))
        self.lib_dirs = self.absolutize(kwargs.get('lib_dirs', []))
        self.extra_objs = self.absolutize(kwargs.get('extra_objs', []))
        self.error = kwargs.get('error', None)
        self.libraries = kwargs.get('libraries', [])
        self.cflags = kwargs.get('cflags', [])
        self.ldflags = kwargs.get('ldflags', [])
        self.optional = kwargs.get('optional', False)
        self.needs_ddk = kwargs.get('needs_ddk', False)

reflow_sources = glob.glob(os.path.join(SRC, 'calibre', 'ebooks', 'pdf', '*.cpp'))
reflow_headers = glob.glob(os.path.join(SRC, 'calibre', 'ebooks', 'pdf', '*.h'))
reflow_error = poppler_error if poppler_error else magick_error

pdfreflow_libs = []
if iswindows:
    pdfreflow_libs = ['advapi32', 'User32', 'Gdi32', 'zlib']

icu_libs = ['icudata', 'icui18n', 'icuuc', 'icuio']
icu_cflags = []
if iswindows:
    icu_libs = ['icudt', 'icuin', 'icuuc', 'icuio']
if isosx:
    icu_libs = ['icucore']
    icu_cflags = ['-DU_DISABLE_RENAMING'] # Needed to use system libicucore.dylib


extensions = [

    Extension('speedup',
        ['calibre/utils/speedup.c'],
        ),

    Extension('icu',
        ['calibre/utils/icu.c'],
        libraries=icu_libs,
        lib_dirs=icu_lib_dirs,
        inc_dirs=icu_inc_dirs,
        cflags=icu_cflags
        ),

    Extension('sqlite_custom',
        ['calibre/library/sqlite_custom.c'],
        inc_dirs=sqlite_inc_dirs
        ),

    Extension('chmlib',
            ['calibre/utils/chm/swig_chm.c'],
            libraries=['ChmLib' if iswindows else 'chm'],
            inc_dirs=chmlib_inc_dirs,
            lib_dirs=chmlib_lib_dirs,
            cflags=["-DSWIG_COBJECT_TYPES"]),

    Extension('chm_extra',
            ['calibre/utils/chm/extra.c'],
            libraries=['ChmLib' if iswindows else 'chm'],
            inc_dirs=chmlib_inc_dirs,
            lib_dirs=chmlib_lib_dirs,
            cflags=["-D__PYTHON__"]),

    Extension('magick',
        ['calibre/utils/magick/magick.c'],
        headers=['calibre/utils/magick/magick_constants.h'],
        libraries=magick_libs,
        lib_dirs=magick_lib_dirs,
        inc_dirs=magick_inc_dirs
        ),

    Extension('pdfreflow',
                reflow_sources,
                headers=reflow_headers,
                libraries=poppler_libs+magick_libs+png_libs+ft_libs+jpg_libs+pdfreflow_libs,
                lib_dirs=poppler_lib_dirs+magick_lib_dirs+png_lib_dirs+ft_lib_dirs+jpg_lib_dirs,
                inc_dirs=poppler_inc_dirs+magick_inc_dirs+png_inc_dirs,
                error=reflow_error,
                cflags=poppler_cflags
                ),

    Extension('lzx',
            ['calibre/utils/lzx/lzxmodule.c',
                    'calibre/utils/lzx/compressor.c',
                    'calibre/utils/lzx/lzxd.c',
                    'calibre/utils/lzx/lzc.c',
                    'calibre/utils/lzx/lzxc.c'],
            headers=['calibre/utils/lzx/msstdint.h',
                    'calibre/utils/lzx/lzc.h',
                    'calibre/utils/lzx/lzxmodule.h',
                    'calibre/utils/lzx/system.h',
                    'calibre/utils/lzx/lzxc.h',
                    'calibre/utils/lzx/lzxd.h',
                    'calibre/utils/lzx/mspack.h'],
            inc_dirs=['calibre/utils/lzx']),

    Extension('fontconfig',
        ['calibre/utils/fonts/fontconfig.c'],
        inc_dirs = [fc_inc],
        libraries=['fontconfig'],
        lib_dirs=[fc_lib],
        error=fc_error),

    Extension('msdes',
                ['calibre/utils/msdes/msdesmodule.c',
                        'calibre/utils/msdes/des.c'],
                headers=['calibre/utils/msdes/spr.h',
                        'calibre/utils/msdes/d3des.h'],
                inc_dirs=['calibre/utils/msdes']),

    Extension('cPalmdoc',
        ['calibre/ebooks/compression/palmdoc.c']),

    Extension('podofo',
                    ['calibre/utils/podofo/podofo.cpp'],
                    libraries=['podofo'],
                    lib_dirs=[podofo_lib],
                    inc_dirs=[podofo_inc],
                    optional=True,
                    error=podofo_error),

    Extension('pictureflow',
                ['calibre/gui2/pictureflow/pictureflow.cpp'],
                inc_dirs = ['calibre/gui2/pictureflow'],
                headers = ['calibre/gui2/pictureflow/pictureflow.h'],
                sip_files = ['calibre/gui2/pictureflow/pictureflow.sip']
                ),

    Extension('progress_indicator',
                ['calibre/gui2/progress_indicator/QProgressIndicator.cpp'],
                inc_dirs = ['calibre/gui2/progress_indicator'],
                headers = ['calibre/gui2/progress_indicator/QProgressIndicator.h'],
                sip_files = ['calibre/gui2/progress_indicator/QProgressIndicator.sip']
                ),

    ]


if iswindows:
    extensions.append(Extension('winutil',
                ['calibre/utils/windows/winutil.c'],
                libraries=['shell32', 'setupapi', 'wininet'],
                cflags=['/X']
                ))

if isosx:
    extensions.append(Extension('usbobserver',
                ['calibre/devices/usbobserver/usbobserver.c'],
                ldflags=['-framework', 'IOKit'])
            )

if isunix:
    cc = os.environ.get('CC', 'gcc')
    cxx = os.environ.get('CXX', 'g++')
    cflags = os.environ.get('OVERRIDE_CFLAGS',
        '-O3 -Wall -DNDEBUG -fno-strict-aliasing -pipe')
    cflags = shlex.split(cflags) + ['-fPIC']
    ldflags = os.environ.get('OVERRIDE_LDFLAGS', '-Wall')
    ldflags = shlex.split(ldflags)
    cflags += shlex.split(os.environ.get('CFLAGS', ''))
    ldflags += shlex.split(os.environ.get('LDFLAGS', ''))

if islinux:
    cflags.append('-pthread')
    ldflags.append('-shared')
    cflags.append('-I'+sysconfig.get_python_inc())
    ldflags.append('-lpython'+sysconfig.get_python_version())


if isbsd:
    cflags.append('-pthread')
    ldflags.append('-shared')
    cflags.append('-I'+sysconfig.get_python_inc())
    ldflags.append('-lpython'+sysconfig.get_python_version())


if isosx:
    x, p = ('i386', 'x86_64')
    archs = ['-arch', x, '-arch', p, '-isysroot',
                OSX_SDK]
    cflags.append('-D_OSX')
    cflags.extend(archs)
    ldflags.extend(archs)
    ldflags.extend('-bundle -undefined dynamic_lookup'.split())
    cflags.extend(['-fno-common', '-dynamic'])
    cflags.append('-I'+sysconfig.get_python_inc())


if iswindows:
    cc = cxx = msvc.cc
    cflags = '/c /nologo /Ox /MD /W3 /EHsc /DNDEBUG'.split()
    ldflags = '/DLL /nologo /INCREMENTAL:NO /NODEFAULTLIB:libcmt.lib'.split()
    #cflags = '/c /nologo /Ox /MD /W3 /EHsc /Zi'.split()
    #ldflags = '/DLL /nologo /INCREMENTAL:NO /DEBUG'.split()

    for p in win_inc:
        cflags.append('-I'+p)
    for p in win_lib:
        ldflags.append('/LIBPATH:'+p)
    cflags.append('-I%s'%sysconfig.get_python_inc())
    ldflags.append('/LIBPATH:'+os.path.join(sysconfig.PREFIX, 'libs'))


class Build(Command):

    short_description = 'Build calibre C/C++ extension modules'

    description = textwrap.dedent('''\
        calibre depends on several python extensions written in C/C++.
        This command will compile them. You can influence the compile
        process by several environment variables, listed below:

           CC      - C Compiler defaults to gcc
           CXX     - C++ Compiler, defaults to g++
           CFLAGS  - Extra compiler flags
           LDFLAGS - Extra linker flags

           FC_INC_DIR - fontconfig header files
           FC_LIB_DIR - fontconfig library

           POPPLER_INC_DIR - poppler header files
           POPPLER_LIB_DIR - poppler-qt4 library

           PODOFO_INC_DIR - podofo header files
           PODOFO_LIB_DIR - podofo library files

           QMAKE          - Path to qmake
           VS90COMNTOOLS  - Location of Microsoft Visual Studio 9 Tools (windows only)

        ''')

    def add_options(self, parser):
        choices = [e.name for e in extensions]+['all']
        parser.add_option('-1', '--only', choices=choices, default='all',
                help=('Build only the named extension. Available: '+
                    ', '.join(choices)+'. Default:%default'))
        parser.add_option('--no-compile', default=False, action='store_true',
                help='Skip compiling all C/C++ extensions.')

    def run(self, opts):
        if opts.no_compile:
            self.info('--no-compile specified, skipping compilation')
            return
        self.obj_dir = os.path.join(os.path.dirname(SRC), 'build', 'objects')
        if not os.path.exists(self.obj_dir):
            os.makedirs(self.obj_dir)
        for ext in extensions:
            if opts.only != 'all' and opts.only != ext.name:
                continue
            if ext.error is not None:
                if ext.optional:
                    self.warn(ext.error)
                    continue
                else:
                    raise Exception(ext.error)
            dest = self.dest(ext)
            if not os.path.exists(self.d(dest)):
                os.makedirs(self.d(dest))
            self.info('\n####### Building extension', ext.name, '#'*7)
            self.build(ext, dest)

    def dest(self, ext):
        ex = '.pyd' if iswindows else '.so'
        return os.path.join(SRC, 'calibre', 'plugins', ext.name)+ex

    def inc_dirs_to_cflags(self, dirs):
        return ['-I'+x for x in dirs]

    def lib_dirs_to_ldflags(self, dirs):
        pref = '/LIBPATH:' if iswindows else '-L'
        return [pref+x for x in dirs]

    def libraries_to_ldflags(self, dirs):
        pref = '' if iswindows else '-l'
        suff = '.lib' if iswindows else ''
        return [pref+x+suff for x in dirs]

    def build(self, ext, dest):
        if ext.sip_files:
            return self.build_pyqt_extension(ext, dest)
        compiler = cxx if ext.needs_cxx else cc
        linker = msvc.linker if iswindows else compiler
        objects = []
        einc = self.inc_dirs_to_cflags(ext.inc_dirs)
        obj_dir = self.j(self.obj_dir, ext.name)
        if ext.needs_ddk:
            ddk_flags = ['-I'+x for x in win_ddk]
            i = [i for i in range(len(cflags)) if 'VC\\INCLUDE' in cflags[i]][0]
            cflags[i+1:i+2] = ddk_flags
        if not os.path.exists(obj_dir):
            os.makedirs(obj_dir)
        for src in ext.sources:
            obj = self.j(obj_dir, os.path.splitext(self.b(src))[0]+'.o')
            objects.append(obj)
            if self.newer(obj, [src]+ext.headers):
                inf = '/Tp' if src.endswith('.cpp') else '/Tc'
                sinc = [inf+src] if iswindows else ['-c', src]
                oinc = ['/Fo'+obj] if iswindows else ['-o', obj]
                cmd = [compiler] + cflags + ext.cflags + einc + sinc + oinc
                self.info(' '.join(cmd))
                self.check_call(cmd)

        dest = self.dest(ext)
        elib = self.lib_dirs_to_ldflags(ext.lib_dirs)
        xlib = self.libraries_to_ldflags(ext.libraries)
        if self.newer(dest, objects):
            print 'Linking', ext.name
            cmd = [linker]
            if iswindows:
                cmd += ldflags + ext.ldflags + elib + xlib + \
                    ['/EXPORT:init'+ext.name] + objects + ext.extra_objs + ['/OUT:'+dest]
            else:
                cmd += objects + ext.extra_objs + ['-o', dest] + ldflags + ext.ldflags + elib + xlib
            self.info('\n\n', ' '.join(cmd), '\n\n')
            self.check_call(cmd)
            if iswindows:
                #manifest = dest+'.manifest'
                #cmd = [MT, '-manifest', manifest, '-outputresource:%s;2'%dest]
                #self.info(*cmd)
                #self.check_call(cmd)
                #os.remove(manifest)
                for x in ('.exp', '.lib'):
                    x = os.path.splitext(dest)[0]+x
                    if os.path.exists(x):
                        os.remove(x)

    def check_call(self, *args, **kwargs):
        """print cmdline if an error occured

        If something is missing (qmake e.g.) you get a non-informative error
         self.check_call(qmc + [ext.name+'.pro'])
         so you would have to look a the source to see the actual command.
        """
        try:
            subprocess.check_call(*args, **kwargs)
        except:
            cmdline = ' '.join(['"%s"' % (arg) if ' ' in arg else arg for arg in args[0]])
            print "Error while executing: %s\n" % (cmdline)
            raise

    def build_qt_objects(self, ext):
        obj_pat = 'release\\*.obj' if iswindows else '*.o'
        objects = glob.glob(obj_pat)
        if not objects or self.newer(objects, ext.sources+ext.headers):
            archs = 'x86 x86_64'
            pro = textwrap.dedent('''\
                TARGET   = %s
                TEMPLATE = lib
                HEADERS  = %s
                SOURCES  = %s
                VERSION  = 1.0.0
                CONFIG   += %s
            ''')%(ext.name, ' '.join(ext.headers), ' '.join(ext.sources), archs)
            pro = pro.replace('\\', '\\\\')
            open(ext.name+'.pro', 'wb').write(pro)
            qmc = [QMAKE, '-o', 'Makefile']
            if iswindows:
                qmc += ['-spec', 'win32-msvc2008']
            self.check_call(qmc + [ext.name+'.pro'])
            self.check_call([make, '-f', 'Makefile'])
            objects = glob.glob(obj_pat)
        return list(map(self.a, objects))

    def build_pyqt_extension(self, ext, dest):
        pyqt_dir = self.j(self.d(self.SRC), 'build', 'pyqt')
        src_dir = self.j(pyqt_dir, ext.name)
        qt_dir  = self.j(src_dir, 'qt')
        if not self.e(qt_dir):
            os.makedirs(qt_dir)
        cwd = os.getcwd()
        try:
            os.chdir(qt_dir)
            qt_objects = self.build_qt_objects(ext)
        finally:
            os.chdir(cwd)

        sip_files = ext.sip_files
        ext.sip_files = []
        sipf = sip_files[0]
        sbf = self.j(src_dir, self.b(sipf)+'.sbf')
        if self.newer(sbf, [sipf]+ext.headers):
            exe = '.exe' if iswindows else ''
            cmd = [pyqt.sip_bin+exe, '-w', '-c', src_dir, '-b', sbf, '-I'+\
                    pyqt.pyqt_sip_dir] + shlex.split(pyqt.pyqt_sip_flags) + [sipf]
            self.info(' '.join(cmd))
            self.check_call(cmd)
        module = self.j(src_dir, self.b(dest))
        if self.newer(dest, [sbf]+qt_objects):
            mf = self.j(src_dir, 'Makefile')
            makefile = QtGuiModuleMakefile(configuration=pyqt, build_file=sbf,
                    makefile=mf, universal=OSX_SDK, qt=1)
            makefile.extra_lflags = qt_objects
            makefile.extra_include_dirs = ext.inc_dirs
            makefile.generate()

            self.check_call([make, '-f', mf], cwd=src_dir)
            shutil.copy2(module, dest)

    def clean(self):
        for ext in extensions:
            dest = self.dest(ext)
            for x in (dest, dest+'.manifest'):
                if os.path.exists(x):
                    os.remove(x)
        build_dir = self.j(self.d(self.SRC), 'build')
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)


class BuildPDF2XML(Command):

    description = 'Build command line pdf2xml utility'

    def run(self, opts):
        dest = os.path.expanduser('~/bin/pdf2xml')
        if iswindows:
            dest = r'C:\cygwin\home\kovid\sw\bin\pdf2xml.exe'
        odest = self.j(self.d(self.SRC), 'build', 'objects', 'pdf2xml')
        if not os.path.exists(odest):
            os.makedirs(odest)

        objects = []
        for src in reflow_sources:
            if src.endswith('python.cpp'):
                continue
            obj = self.j(odest, self.b(src+('.obj' if iswindows else '.o')))
            if self.newer(obj, [src]+reflow_headers):
                cmd = [cxx, '-pthread', '-pedantic', '-ggdb', '-c', '-Wall', '-I/usr/include/poppler',
                        '-I/usr/include/ImageMagick',
                        '-DPDF2XML', '-o', obj, src]
                if iswindows:
                    cmd = [cxx, '/c', '/MD', '/W3', '/EHsc', '/Zi', '/DPDF2XML']
                    cmd += ['-I'+x for x in poppler_inc_dirs+magick_inc_dirs]
                    cmd += ['/Fo'+obj, src]
                self.info(*cmd)
                self.check_call(cmd)
            objects.append(obj)

        if self.newer(dest, objects):
            cmd = ['g++', '-ggdb', '-o', dest]+objects+['-lpoppler', '-lMagickWand',
            '-lpng', '-lpthread']
            if iswindows:
                cmd = [msvc.linker] + '/INCREMENTAL:NO /DEBUG /NODEFAULTLIB:libcmt.lib'.split()
                cmd += ['/LIBPATH:'+x for x in magick_lib_dirs+poppler_lib_dirs]
                cmd += [x+'.lib' for x in
                        png_libs+magick_libs+poppler_libs+ft_libs+jpg_libs+pdfreflow_libs]
                cmd += ['/OUT:'+dest] + objects
            self.info(*cmd)
            self.check_call(cmd)

        self.info('Binary installed as', dest)



