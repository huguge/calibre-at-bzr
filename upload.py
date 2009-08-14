from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import shutil, os, glob, re, cStringIO, sys, tempfile, time, textwrap, socket, \
       struct, subprocess
from datetime import datetime
from setuptools.command.build_py import build_py as _build_py, convert_path
from distutils.core import Command
from subprocess import check_call, call, Popen
from distutils.command.build import build as _build

raw = open(os.path.join('src', 'calibre', 'constants.py'), 'rb').read()
__version__ = re.search(r'__version__\s+=\s+[\'"]([^\'"]+)[\'"]', raw).group(1)
__appname__ = re.search(r'__appname__\s+=\s+[\'"]([^\'"]+)[\'"]', raw).group(1)

PREFIX = "/var/www/calibre.kovidgoyal.net"
DOWNLOADS = PREFIX+"/htdocs/downloads"
BETAS = DOWNLOADS +'/betas'
DOCS = PREFIX+"/htdocs/apidocs"
USER_MANUAL = PREFIX+'/htdocs/user_manual'
HTML2LRF = "src/calibre/ebooks/lrf/html/demo"
TXT2LRF  = "src/calibre/ebooks/lrf/txt/demo"
MOBILEREAD = 'ftp://dev.mobileread.com/calibre/'


def get_ip_address(ifname):
    import fcntl
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

try:
    HOST=get_ip_address('eth0')
except:
    try:
        HOST=get_ip_address('wlan0')
    except:
        HOST='unknown'

def newer(targets, sources):
    '''
    Return True if sources is newer that targets or if targets
    does not exist.
    '''
    for f in targets:
        if not os.path.exists(f):
            return True
    ttimes = map(lambda x: os.stat(x).st_mtime, targets)
    stimes = map(lambda x: os.stat(x).st_mtime, sources)
    newest_source, oldest_target = max(stimes), min(ttimes)
    return newest_source > oldest_target


class OptionlessCommand(Command):
    user_options = []
    def initialize_options(self): pass
    def finalize_options(self): pass

    def run(self):
        for cmd_name in self.get_sub_commands():
            self.run_command(cmd_name)


class sdist(OptionlessCommand):

    description = 'Create a source distribution using bzr'

    def run(self):
        name = os.path.join('dist', '%s-%s.tar.gz'%(__appname__, __version__))
        check_call(('bzr export '+name).split())
        self.distribution.dist_files.append(('sdist', '', name))
        print 'Source distribution created in', os.path.abspath(name)

class pot(OptionlessCommand):
    description = '''Create the .pot template for all translatable strings'''

    PATH = os.path.join('src', __appname__, 'translations')

    def source_files(self):
        ans = []
        for root, _, files in os.walk(os.path.dirname(self.PATH)):
            for name in files:
                if name.endswith('.py'):
                    ans.append(os.path.abspath(os.path.join(root, name)))
        return ans


    def run(self):
        sys.path.insert(0, os.path.abspath(self.PATH))
        try:
            pygettext = __import__('pygettext', fromlist=['main']).main
            files = self.source_files()
            buf = cStringIO.StringIO()
            print 'Creating translations template'
            tempdir = tempfile.mkdtemp()
            pygettext(buf, ['-k', '__', '-p', tempdir]+files)
            src = buf.getvalue()
            pot = os.path.join(self.PATH, __appname__+'.pot')
            f = open(pot, 'wb')
            f.write(src)
            f.close()
            print 'Translations template:', os.path.abspath(pot)
            return pot
        finally:
            sys.path.remove(os.path.abspath(self.PATH))

class manual(OptionlessCommand):

    description='''Build the User Manual '''

    def run(self):
        cwd = os.path.abspath(os.getcwd())
        os.chdir(os.path.join('src', 'calibre', 'manual'))
        try:
            for d in ('.build', 'cli'):
                if os.path.exists(d):
                    shutil.rmtree(d)
                os.makedirs(d)
            if not os.path.exists('.build'+os.sep+'html'):
                os.makedirs('.build'+os.sep+'html')
            check_call(['sphinx-build', '-b', 'custom', '-d',
                                   '.build/doctrees', '.', '.build/html'])
        finally:
            os.chdir(cwd)

    @classmethod
    def clean(cls):
        path = os.path.join('src', 'calibre', 'manual', '.build')
        if os.path.exists(path):
            shutil.rmtree(path)

class resources(OptionlessCommand):
    description='''Compile various resource files used in calibre. '''

    RESOURCES = dict(
        opf_template    = 'ebooks/metadata/opf.xml',
        ncx_template    = 'ebooks/metadata/ncx.xml',
        fb2_xsl         = 'ebooks/fb2/fb2.xsl',
        metadata_sqlite = 'library/metadata_sqlite.sql',
        jquery          = 'gui2/viewer/jquery.js',
        jquery_scrollTo = 'gui2/viewer/jquery_scrollTo.js',
        html_css        = 'ebooks/oeb/html.css',
    )

    DEST = os.path.join('src', __appname__, 'resources.py')

    def get_qt_translations(self):
        data = {}
        translations_found = False
        for TPATH in ('/usr/share/qt4/translations', '/usr/lib/qt4/translations'):
            if os.path.exists(TPATH):
                files = glob.glob(TPATH + '/qt_??.qm')
                for f in files:
                    key = os.path.basename(f).partition('.')[0]
                    data[key] = f
                translations_found = True
                break
        if not translations_found:
            print 'WARNING: Could not find Qt transations'
        return data

    def get_static_resources(self):
        sdir = os.path.join('src', 'calibre', 'library', 'static')
        resources, max = {}, 0
        for f in os.listdir(sdir):
            resources[f] = self.get(os.path.join(sdir, f))
            mtime = os.stat(os.path.join(sdir, f)).st_mtime
            max = mtime if mtime > max else max
        return resources, max

    def get_recipes(self):
        sdir = os.path.join('src', 'calibre', 'web', 'feeds', 'recipes')
        resources, max = {}, 0
        for f in os.listdir(sdir):
            if f.endswith('.py') and f != '__init__.py':
                resources[f.replace('.py', '')] = self.get(os.path.join(sdir, f))
                mtime = os.stat(os.path.join(sdir, f)).st_mtime
                max = mtime if mtime > max else max
        return resources, max

    def get_hyphenate(self):
        sdir = os.path.join('src', 'calibre', 'gui2', 'viewer', 'hyphenate')
        resources, max = {}, 0
        languages = set([])
        for f in glob.glob(os.path.join(sdir, 'patterns', '*.js')) + \
                [os.path.join(sdir, 'Hyphenator.js')]:
                f = os.path.abspath(f)
                b = os.path.basename(f)
                resources[b] = self.get(f)
                if b != 'Hyphenator.js':
                    languages.add(b.split('.')[0])
                mtime = os.stat(f).st_mtime
                max = mtime if mtime > max else max
        resources['languages'] = ','.join(languages)
        return resources, max

    def run(self):
        data, dest, RESOURCES = {}, self.DEST, self.RESOURCES
        for key in RESOURCES:
            path = RESOURCES[key]
            if not os.path.isabs(path):
                RESOURCES[key] = os.path.join('src', __appname__, path)
        translations = self.get_qt_translations()
        RESOURCES.update(translations)
        static, smax = self.get_static_resources()
        recipes, rmax = self.get_recipes()
        hyphenate, hmax = self.get_hyphenate()
        amax = max(rmax, smax, hmax, os.stat(__file__).st_mtime)
        if newer([dest], RESOURCES.values()) or os.stat(dest).st_mtime < amax:
            print 'Compiling resources...'
            with open(dest, 'wb') as f:
                for key in RESOURCES:
                    data = self.get(RESOURCES[key])
                    f.write(key + ' = ' + repr(data)+'\n\n')
                f.write('server_resources = %s\n\n'%repr(static))
                f.write('recipes = %s\n\n'%repr(recipes))
                f.write('hyphenate = %s\n\n'%repr(hyphenate))
                f.write('build_time = "%s"\n\n'%time.strftime('%d %m %Y %H%M%S'))
        else:
            print 'Resources are up to date'

    def get(self, path):
        data = open(path, 'rb').read()
        if path.endswith('.js') and not path.endswith('date.js'):
            data = self.js_minify(data)
        return data

    def js_minify(self, data):
        from jsmin import jsmin
        return jsmin(data)

    @classmethod
    def clean(cls):
        path = cls.DEST
        for path in glob.glob(path+'*'):
            if os.path.exists(path):
                os.remove(path)

class translations(OptionlessCommand):
    description='''Compile the translations'''
    PATH = os.path.join('src', __appname__, 'translations')
    DEST = os.path.join(PATH, 'compiled.py')

    def run(self):
        sys.path.insert(0, os.path.abspath(self.PATH))
        try:
            files = glob.glob(os.path.join(self.PATH, '*.po'))
            if newer([self.DEST], files):
                msgfmt = __import__('msgfmt', fromlist=['main']).main
                translations = {}
                print 'Compiling translations...'
                for po in files:
                    lang = os.path.basename(po).partition('.')[0]
                    buf = cStringIO.StringIO()
                    print 'Compiling', lang
                    msgfmt(buf, [po])
                    translations[lang] = buf.getvalue()
                open(self.DEST, 'wb').write('translations = '+repr(translations))
            else:
                print 'Translations up to date'
        finally:
            sys.path.remove(os.path.abspath(self.PATH))


    @classmethod
    def clean(cls):
        path = cls.DEST
        if os.path.exists(path):
            os.remove(path)


class gui(OptionlessCommand):
    description='''Compile all GUI forms and images'''
    PATH  = os.path.join('src', __appname__, 'gui2')
    IMAGES_DEST = os.path.join(PATH, 'images_rc.py')
    QRC = os.path.join(PATH, 'images.qrc')

    @classmethod
    def find_forms(cls):
        forms = []
        for root, _, files in os.walk(cls.PATH):
            for name in files:
                if name.endswith('.ui'):
                    forms.append(os.path.abspath(os.path.join(root, name)))

        return forms

    @classmethod
    def form_to_compiled_form(cls, form):
        return form.rpartition('.')[0]+'_ui.py'

    def run(self):
        self.build_forms()
        self.build_images()

    def build_images(self):
        cwd, images = os.getcwd(), os.path.basename(self.IMAGES_DEST)
        try:
            os.chdir(self.PATH)
            sources, files = [], []
            for root, _, files in os.walk('images'):
                for name in files:
                    sources.append(os.path.join(root, name))
            if newer([images], sources):
                print 'Compiling images...'
                for s in sources:
                    alias = ' alias="library"' if s.endswith('images'+os.sep+'library.png') else ''
                    files.append('<file%s>%s</file>'%(alias, s))
                manifest = '<RCC>\n<qresource prefix="/">\n%s\n</qresource>\n</RCC>'%'\n'.join(files)
                with open('images.qrc', 'wb') as f:
                    f.write(manifest)
                try:
                    check_call(['pyrcc4', '-o', images, 'images.qrc'])
                except:
                    import traceback
                    traceback.print_exc()
                    raise Exception('You do not have pyrcc4 in your PATH. '
                                    'Install the PyQt4 development tools.')
            else:
                print 'Images are up to date'
        finally:
            os.chdir(cwd)


    def build_forms(self):
        from PyQt4.uic import compileUi
        forms = self.find_forms()
        for form in forms:
            compiled_form = self.form_to_compiled_form(form)
            if not os.path.exists(compiled_form) or os.stat(form).st_mtime > os.stat(compiled_form).st_mtime:
                print 'Compiling form', form
                buf = cStringIO.StringIO()
                compileUi(form, buf)
                dat = buf.getvalue()
                dat = dat.replace('__appname__', __appname__)
                dat = dat.replace('import images_rc', 'from calibre.gui2 import images_rc')
                dat = dat.replace('from library import', 'from calibre.gui2.library import')
                dat = dat.replace('from widgets import', 'from calibre.gui2.widgets import')
                dat = dat.replace('from convert.xpath_wizard import',
                    'from calibre.gui2.convert.xpath_wizard import')
                dat = re.compile(r'QtGui.QApplication.translate\(.+?,\s+"(.+?)(?<!\\)",.+?\)', re.DOTALL).sub(r'_("\1")', dat)
                dat = dat.replace('_("MMM yyyy")', '"MMM yyyy"')

                # Workaround bug in Qt 4.4 on Windows
                if form.endswith('dialogs%sconfig.ui'%os.sep) or form.endswith('dialogs%slrf_single.ui'%os.sep):
                    print 'Implementing Workaround for buggy pyuic in form', form
                    dat = re.sub(r'= QtGui\.QTextEdit\(self\..*?\)', '= QtGui.QTextEdit()', dat)
                    dat = re.sub(r'= QtGui\.QListWidget\(self\..*?\)', '= QtGui.QListWidget()', dat)

                if form.endswith('viewer%smain.ui'%os.sep):
                    print 'Promoting WebView'
                    dat = dat.replace('self.view = QtWebKit.QWebView(', 'self.view = DocumentView(')
                    dat += '\n\nfrom calibre.gui2.viewer.documentview import DocumentView'

                open(compiled_form, 'wb').write(dat)


    @classmethod
    def clean(cls):
        forms = cls.find_forms()
        for form in forms:
            c = cls.form_to_compiled_form(form)
            if os.path.exists(c):
                os.remove(c)
        for x in (cls.IMAGES_DEST, cls.QRC):
            if os.path.exists(x):
                os.remove(x)

class clean(OptionlessCommand):

    description='''Delete all computer generated files in the source tree'''

    def run(self):
        print 'Cleaning...'
        manual.clean()
        gui.clean()
        translations.clean()
        resources.clean()

        for f in glob.glob(os.path.join('src', 'calibre', 'plugins', '*')):
            os.remove(f)
        for root, _, files in os.walk('.'):
            for name in files:
                for t in ('.pyc', '.pyo', '~'):
                    if name.endswith(t):
                        os.remove(os.path.join(root, name))
                        break

        for dir in ('build', 'dist', os.path.join('src', 'calibre.egg-info')):
            shutil.rmtree(dir, ignore_errors=True)

class build_py(_build_py):

    def find_data_files(self, package, src_dir):
        """
        Return filenames for package's data files in 'src_dir'
        Modified to treat data file specs as paths not globs
        """
        globs = (self.package_data.get('', [])
                 + self.package_data.get(package, []))
        files = self.manifest_files.get(package, [])[:]
        for pattern in globs:
            # Each pattern has to be converted to a platform-specific path
            pattern = os.path.join(src_dir, convert_path(pattern))
            next = glob.glob(pattern)
            files.extend(next if next else [pattern])

        return self.exclude_data_files(package, src_dir, files)

class build(_build):

    sub_commands = [
                     ('resources',    lambda self : 'CALIBRE_BUILDBOT' not in os.environ.keys()),
                     ('translations', lambda self : 'CALIBRE_BUILDBOT' not in os.environ.keys()),
                     ('gui',          lambda self : 'CALIBRE_BUILDBOT' not in os.environ.keys()),
                     ('build_ext',    lambda self: True),
                     ('build_py',     lambda self: True),
                     ('build_clib',    _build.has_c_libraries),
                     ('build_scripts', _build.has_scripts),
                   ]


class update(OptionlessCommand):

    description = 'Rebuild plugins and run develop. Should be called after ' +\
                  ' a version update.'

    def run(self):
        for x in ['build', 'dist'] + \
            glob.glob(os.path.join('src', 'calibre', 'plugins', '*')):
            if os.path.exists(x):
                if os.path.isdir(x):
                    check_call('sudo rm -rf '+x, shell=True)
                    os.mkdir(x)
                else:
                    os.remove(x)

        check_call('python setup.py build_ext build'.split())
        check_call('sudo python setup.py develop'.split())

class tag_release(OptionlessCommand):

    description = 'Tag a new release in bzr'

    def run(self):
        print 'Tagging release'
        check_call(('bzr tag '+__version__).split())
        check_call('bzr commit --unchanged -m'.split() + ['IGN:Tag release'])


class upload_demo(OptionlessCommand):

    description = 'Rebuild and upload various demos'

    def run(self):
        check_call(
           '''ebook-convert %s/demo.html /tmp/html2lrf.lrf '''
           '''--title='Demonstration of html2lrf' --authors='Kovid Goyal' '''
           '''--header '''
           '''--serif-family "/usr/share/fonts/corefonts, Times New Roman" '''
           '''--mono-family  "/usr/share/fonts/corefonts, Andale Mono" '''
           ''''''%(HTML2LRF,), shell=True)

        check_call(
            'cd src/calibre/ebooks/lrf/html/demo/ && '
            'zip -j /tmp/html-demo.zip * /tmp/html2lrf.lrf', shell=True)

        check_call('scp /tmp/html-demo.zip divok:%s/'%(DOWNLOADS,), shell=True)


def installer_name(ext):
    if ext in ('exe', 'dmg'):
        return 'dist/%s-%s.%s'%(__appname__, __version__, ext)
    return 'dist/%s-%s-i686.%s'%(__appname__, __version__, ext)


class build_linux(OptionlessCommand):
    description = 'Build linux installer'
    def run(self):
        installer = installer_name('tar.bz2')
        locals = {}
        exec open('installer/linux/freeze.py') in locals
        locals['freeze']()
        if not os.path.exists(installer):
            raise Exception('Failed to build installer '+installer)
        return os.path.basename(installer)

class VMInstaller(OptionlessCommand):

    user_options = [('dont-shutdown', 'd', 'Dont shutdown Vm after build')]
    boolean_options = ['dont-shutdown']

    def initialize_options(self):
        self.dont_shutdown = False

    BUILD_SCRIPT = textwrap.dedent('''\
        #!/bin/bash
        export CALIBRE_BUILDBOT=1
        cd ~/build && \
        rsync -avz --exclude src/calibre/plugins \
               --exclude calibre/src/calibre.egg-info --exclude docs \
               --exclude .bzr --exclude .build --exclude build --exclude dist \
               --exclude "*.pyc" --exclude "*.pyo" \
               rsync://%(host)s/work/%(project)s . && \
        cd %(project)s && \
        %%s && \
        rm -rf build/* dist/* && \
        %%s %%s
        '''%dict(host=HOST, project=__appname__))

    def get_build_script(self, subs):
        return self.BUILD_SCRIPT%subs

    def start_vm(self, ssh_host, build_script, sleep=75):
        build_script = self.get_build_script(build_script)
        vmware = ('vmware', '-q', '-x', '-n', self.VM)
        Popen(vmware)
        t = tempfile.NamedTemporaryFile(suffix='.sh')
        t.write(build_script)
        t.flush()
        print 'Waiting for VM to startup'
        while call('ping -q -c1 '+ssh_host, shell=True,
                   stdout=open('/dev/null', 'w')) != 0:
            time.sleep(5)
        time.sleep(20)
        print 'Trying to SSH into VM'
        check_call(('scp', t.name, ssh_host+':build-calibre'))
        check_call('ssh -t %s bash build-calibre'%ssh_host, shell=True)

class build_windows(VMInstaller):
    description = 'Build windows installer'
    VM = '/mnt/backup/calibre_windows_xp_home/calibre_windows_xp_home.vmx'
    if not os.path.exists(VM):
        VM = '/home/kovid/calibre_windows_xp_home/calibre_windows_xp_home.vmx'

    def run(self):
        installer = installer_name('exe')
        self.start_vm('windows', ('python setup.py develop',
                                  'python',
                                  r'installer\\windows\\freeze.py'))
        if os.path.exists('build/py2exe'):
            shutil.rmtree('build/py2exe')
        check_call(('scp', '-rp', 'windows:build/%s/build/py2exe'%__appname__,
                     'build'))
        if not os.path.exists('build/py2exe'):
            raise Exception('Failed to run py2exe')
        if not self.dont_shutdown:
            Popen(('ssh', 'windows', 'shutdown', '-s', '-t', '0'))
        self.run_windows_install_jammer(installer)
        return os.path.basename(installer)

    @classmethod
    def run_windows_install_jammer(self, installer):
        ibp = os.path.abspath('installer/windows')
        sys.path.insert(0, ibp)
        build_installer = __import__('build_installer')
        sys.path.remove(ibp)
        build_installer.run_install_jammer(
                                    installer_name=os.path.basename(installer))
        if not os.path.exists(installer):
            raise Exception('Failed to run installjammer')


class build_osx(VMInstaller):
    description = 'Build OS X app bundle'
    VM = '/mnt/backup/calibre_os_x/Mac OSX.vmx'
    if not os.path.exists(VM):
        VM = '/home/kovid/calibre_os_x/Mac OSX.vmx'

    def get_build_script(self, subs):
        return (self.BUILD_SCRIPT%subs).replace('rm ', 'sudo rm ')

    def run(self):
        installer = installer_name('dmg')
        python = '/Library/Frameworks/Python.framework/Versions/Current/bin/python'
        self.start_vm('osx', ('sudo %s setup.py develop'%python, python,
                              'installer/osx/freeze.py'))
        check_call(('scp', 'osx:build/calibre/dist/*.dmg', 'dist'))
        if not os.path.exists(installer):
            raise Exception('Failed to build installer '+installer)
        if not self.dont_shutdown:
            Popen(('ssh', 'osx', 'sudo', '/sbin/shutdown', '-h', 'now'))
        return os.path.basename(installer)



class upload_installers(OptionlessCommand):
    description = 'Upload any installers present in dist/'
    def curl_list_dir(self, url=MOBILEREAD, listonly=1):
        import pycurl
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(c.FTP_USE_EPSV, 1)
        c.setopt(c.NETRC, c.NETRC_REQUIRED)
        c.setopt(c.FTPLISTONLY, listonly)
        c.setopt(c.FTP_CREATE_MISSING_DIRS, 1)
        b = cStringIO.StringIO()
        c.setopt(c.WRITEFUNCTION, b.write)
        c.perform()
        c.close()
        return b.getvalue().split() if listonly else b.getvalue().splitlines()

    def curl_delete_file(self, path, url=MOBILEREAD):
        import pycurl
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(c.FTP_USE_EPSV, 1)
        c.setopt(c.NETRC, c.NETRC_REQUIRED)
        print 'Deleting file %s on %s'%(path, url)
        c.setopt(c.QUOTE, ['dele '+ path])
        c.perform()
        c.close()


    def curl_upload_file(self, stream, url):
        import pycurl
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(pycurl.UPLOAD, 1)
        c.setopt(c.NETRC, c.NETRC_REQUIRED)
        c.setopt(pycurl.READFUNCTION, stream.read)
        stream.seek(0, 2)
        c.setopt(pycurl.INFILESIZE_LARGE, stream.tell())
        stream.seek(0)
        c.setopt(c.NOPROGRESS, 0)
        c.setopt(c.FTP_CREATE_MISSING_DIRS, 1)
        print 'Uploading file %s to url %s' % (getattr(stream, 'name', ''), url)
        try:
            c.perform()
            c.close()
        except:
            pass
        files = self.curl_list_dir(listonly=0)
        for line in files:
            line = line.split()
            if url.endswith(line[-1]):
                size = long(line[4])
                stream.seek(0,2)
                if size != stream.tell():
                    raise RuntimeError('curl failed to upload %s correctly'%getattr(stream, 'name', ''))

    def upload_installer(self, name):
        if not os.path.exists(name):
            return
        bname = os.path.basename(name)
        pat = re.compile(bname.replace(__version__, r'\d+\.\d+\.\d+'))
        for f in self.curl_list_dir():
            if pat.search(f):
                self.curl_delete_file('/calibre/'+f)
        self.curl_upload_file(open(name, 'rb'), MOBILEREAD+os.path.basename(name))

    def run(self):
        print 'Uploading installers...'
        for i in ('dmg', 'exe', 'tar.bz2'):
            self.upload_installer(installer_name(i))

        check_call('''ssh divok echo %s \\> %s/latest_version'''\
                   %(__version__, DOWNLOADS), shell=True)

class upload_user_manual(OptionlessCommand):
    description = 'Build and upload the User Manual'
    sub_commands = [('manual', None)]

    def run(self):
        OptionlessCommand.run(self)
        check_call(' '.join(['scp', '-r', 'src/calibre/manual/.build/html/*',
                    'divok:%s'%USER_MANUAL]), shell=True)

class upload_to_pypi(OptionlessCommand):
    description = 'Upload eggs and source to PyPI'
    def run(self):
        check_call('python setup.py register'.split())
        check_call('rm -f dist/*', shell=True)
        check_call('python setup.py build_ext bdist_egg --exclude-source-files upload'.split())
        check_call('python setup.py sdist upload'.split())

class stage3(OptionlessCommand):
    description = 'Stage 3 of the build process'
    sub_commands = [
                    ('upload_installers', None),
                    ('upload_user_manual', None),
                    ('upload_to_pypi', None),
                    ('upload_rss', None),
                    ]

    @classmethod
    def misc(cls):
        check_call('ssh divok rm -f %s/calibre-\*.tar.gz'%DOWNLOADS, shell=True)
        check_call('scp dist/calibre-*.tar.gz divok:%s/'%DOWNLOADS, shell=True)
        check_call('gpg --armor --detach-sign dist/calibre-*.tar.gz',
                shell=True)
        check_call('scp dist/calibre-*.tar.gz.asc divok:%s/signatures/'%DOWNLOADS,
                shell=True)
        check_call('''rm -rf dist/* build/*''', shell=True)
        check_call('ssh divok bzr update /var/www/calibre.kovidgoyal.net/calibre/',
                   shell=True)
        check_call('ssh divok bzr update /usr/local/calibre',
                   shell=True)


    def run(self):
        OptionlessCommand.run(self)
        self.misc()

class stage2(OptionlessCommand):
    description = 'Stage 2 of the build process'
    sub_commands = [
                    ('build_linux', None),
                    ('build_windows', None),
                    ('build_osx', None)
                    ]

    def run(self):
        check_call('rm -rf dist/*', shell=True)
        OptionlessCommand.run(self)

class stage1(OptionlessCommand):
    description = 'Stage 1 of the build process'
    sub_commands = [
                ('update', None),
                ('tag_release', None),
                ('upload_demo', None),
                ]

class betas(OptionlessCommand):
    description = 'Build an upload beta builds to the servers'

    sub_commands = [ ('update', None), ('stage2', None) ]

    def run(self):
        OptionlessCommand.run(self)
        check_call('scp dist/* divok:'+BETAS, shell=True)

class upload(OptionlessCommand):
    description = 'Build and upload calibre to the servers'

    sub_commands = [
            ('pot', None),
            ('stage1', None),
            ('stage2', None),
            ('stage3', None)
            ]

try:
    class upload_rss(OptionlessCommand):

        from bzrlib import log as blog

        class ChangelogFormatter(blog.LogFormatter):
            supports_tags = True
            supports_merge_revisions = False
            _show_advice = False

            def __init__(self, num_of_versions=20):
                from calibre.utils.rss_gen import RSS2
                self.num_of_versions = num_of_versions
                self.rss = RSS2(
                                title = 'calibre releases',
                                link  = 'http://calibre.kovidgoyal.net/wiki/Changelog',
                                description = 'Latest release of calibre',
                                lastBuildDate = datetime.utcnow()
                                )
                self.current_entry = None

            def log_revision(self, r):
                from calibre.utils.rss_gen import RSSItem, Guid
                if len(self.rss.items) > self.num_of_versions-1:
                    return
                msg = r.rev.message
                match = re.match(r'version\s+(\d+\.\d+.\d+)', msg)

                if match:
                    if self.current_entry is not None:
                        mkup = '<div><ul>%s</ul></div>'
                        self.current_entry.description = mkup%(''.join(
                                    self.current_entry.description))
                        if match.group(1) == '0.5.14':
                            self.current_entry.description = \
                            '''<div>See <a href="http://calibre.kovidgoyal.net/new_in_6">New in
                            6</a></div>'''
                        self.rss.items.append(self.current_entry)
                    timestamp = r.rev.timezone + r.rev.timestamp
                    self.current_entry = RSSItem(
                            title = 'calibre %s released'%match.group(1),
                            link  = 'http://calibre.kovidgoyal.net/download',
                            guid = Guid(match.group(), False),
                            pubDate = datetime(*time.gmtime(timestamp)[:6]),
                            description = []
                    )
                elif self.current_entry is not None:
                    if re.search(r'[a-zA-Z]', msg) and len(msg.strip()) > 5:
                        if 'translation' not in msg and not msg.startswith('IGN'):
                            msg = msg.replace('<', '&lt;').replace('>', '&gt;')
                            msg = re.sub('#(\d+)', r'<a href="http://calibre.kovidgoyal.net/ticket/\1">#\1</a>',
                                         msg)

                            self.current_entry.description.append(
                                            '<li>%s</li>'%msg.strip())


        def run(self):
            from bzrlib import log, branch
            bzr_path = os.path.expanduser('~/work/calibre')
            b = branch.Branch.open(bzr_path)
            lf = upload_rss.ChangelogFormatter()
            log.show_log(b, lf)
            lf.rss.write_xml(open('/tmp/releases.xml', 'wb'))
            subprocess.check_call('scp /tmp/releases.xml divok:/var/www/calibre.kovidgoyal.net/htdocs/downloads'.split())
except ImportError:
    upload_rss = None

