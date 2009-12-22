#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

__all__ = [
        'pot', 'translations', 'get_translations', 'iso639',
        'build', 'build_pdf2xml',
        'gui',
        'develop', 'install',
        'resources',
        'check',
        'sdist',
        'manual', 'tag_release',
        'pypi_register', 'pypi_upload', 'upload_to_server',
        'upload_user_manual', 'upload_to_mobileread', 'upload_demo',
        'upload_to_sourceforge', 'upload_to_google_code',
        'linux32', 'linux64', 'linux', 'linux_freeze', 'linux_freeze2',
        'osx32_freeze', 'osx32', 'osx', 'rsync',
        'win32_freeze', 'win32', 'win',
        'stage1', 'stage2', 'stage3', 'stage4', 'publish'
        ]


from setup.translations import POT, GetTranslations, Translations, ISO639
pot = POT()
translations = Translations()
get_translations = GetTranslations()
iso639 = ISO639()

from setup.extensions import Build, BuildPDF2XML
build = Build()
build_pdf2xml = BuildPDF2XML()

from setup.install import Develop, Install, Sdist
develop = Develop()
install = Install()
sdist = Sdist()

from setup.gui import GUI
gui = GUI()

from setup.check import Check
check = Check()

from setup.resources import Resources
resources = Resources()

from setup.publish import Manual, TagRelease, Stage1, Stage2, \
        Stage3, Stage4, Publish
manual = Manual()
tag_release = TagRelease()
stage1 = Stage1()
stage2 = Stage2()
stage3 = Stage3()
stage4 = Stage4()
publish = Publish()

from setup.upload import UploadUserManual, UploadInstallers, UploadDemo, \
        UploadToServer, UploadToSourceForge, UploadToGoogleCode
upload_user_manual = UploadUserManual()
upload_to_mobileread = UploadInstallers()
upload_demo = UploadDemo()
upload_to_server = UploadToServer()
upload_to_sourceforge = UploadToSourceForge()
upload_to_google_code = UploadToGoogleCode()

from setup.installer import Rsync
rsync = Rsync()

from setup.installer.linux import Linux, Linux32, Linux64
linux = Linux()
linux32 = Linux32()
linux64 = Linux64()
from setup.installer.linux.freeze import LinuxFreeze
linux_freeze = LinuxFreeze()
from setup.installer.linux.freeze2 import LinuxFreeze2
linux_freeze2 = LinuxFreeze2()

from setup.installer.osx import OSX, OSX32
osx = OSX()
osx32 = OSX32()
from setup.installer.osx.app.main import OSX32_Freeze
osx32_freeze = OSX32_Freeze()

from setup.installer.windows import Win, Win32
win = Win()
win32 = Win32()
from setup.installer.windows.freeze import Win32Freeze
win32_freeze = Win32Freeze()

from setup.pypi import PyPIRegister, PyPIUpload
pypi_register = PyPIRegister()
pypi_upload   = PyPIUpload()


commands = {}
for x in __all__:
    commands[x] = locals()[x]

command_names = dict(zip(commands.values(), commands.keys()))
