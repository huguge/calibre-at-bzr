#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import subprocess, tempfile, os, time

from setup import Command, installer_name
from setup.build_environment import HOST, PROJECT

class Rsync(Command):

    description = 'Sync source tree from development machine'

    SYNC_CMD = ('rsync -avz --del --exclude src/calibre/plugins '
               '--exclude src/calibre/manual --exclude src/calibre/trac '
               '--exclude .bzr --exclude .build --exclude .svn --exclude build --exclude dist '
               '--exclude "*.pyc" --exclude "*.pyo" --exclude "*.swp" --exclude "*.swo" '
               'rsync://{host}/work/{project} ..')

    def run(self, opts):
        cmd = self.SYNC_CMD.format(host=HOST, project=PROJECT)
        self.info(cmd)
        subprocess.check_call(cmd, shell=True)


class VMInstaller(Command):

    EXTRA_SLEEP = 5

    INSTALLER_EXT = None
    VM = None
    VM_NAME = None
    FREEZE_COMMAND = None
    FREEZE_TEMPLATE = 'python setup.py {freeze_command}'
    SHUTDOWN_CMD = ['sudo', 'poweroff']
    IS_64_BIT = False

    BUILD_CMD = 'ssh -t %s bash build-calibre'
    BUILD_PREFIX = ['#!/bin/bash', 'export CALIBRE_BUILDBOT=1']
    BUILD_RSYNC  = [r'cd ~/build/{project}', Rsync.SYNC_CMD]
    BUILD_CLEAN  = ['rm -rf dist/* build/* src/calibre/plugins/*']
    BUILD_BUILD  = ['python setup.py build',]

    def add_options(self, parser):
        if not parser.has_option('--dont-shutdown'):
            parser.add_option('-s', '--dont-shutdown', default=False,
                action='store_true', help='Dont shutdown the VM after building')
        if not parser.has_option('--vm'):
            parser.add_option('--vm', help='Path to VM launcher script')


    def get_build_script(self):
        ans = '\n'.join(self.BUILD_PREFIX)+'\n\n'
        ans += ' && \\\n'.join(self.BUILD_RSYNC) + ' && \\\n'
        ans += ' && \\\n'.join(self.BUILD_CLEAN) + ' && \\\n'
        ans += ' && \\\n'.join(self.BUILD_BUILD) + ' && \\\n'
        ans += self.FREEZE_TEMPLATE.format(freeze_command=self.FREEZE_COMMAND) + '\n'
        ans = ans.format(project=PROJECT, host=HOST)
        return ans

    def vmware_started(self):
        return 'started' in subprocess.Popen('/etc/init.d/vmware status', shell=True, stdout=subprocess.PIPE).stdout.read()

    def start_vmware(self):
        if not self.vmware_started():
            if os.path.exists('/dev/kvm'):
                subprocess.check_call('sudo rmmod -w kvm-intel kvm', shell=True)
            subprocess.Popen('sudo /etc/init.d/vmware start', shell=True)

    def stop_vmware(self):
            while True:
                try:
                    subprocess.check_call('sudo /etc/init.d/vmware stop', shell=True)
                    break
                except:
                    pass
            while 'vmblock' in open('/proc/modules').read():
                subprocess.check_call('sudo rmmod -f vmblock')


    def run_vm(self):
        self.__p = subprocess.Popen([self.vm])

    def start_vm(self, sleep=75):
        ssh_host = self.VM_NAME
        self.run_vm()
        build_script = self.get_build_script()
        t = tempfile.NamedTemporaryFile(suffix='.sh')
        t.write(build_script)
        t.flush()
        print 'Waiting for VM to startup'
        while subprocess.call('ping -q -c1 '+ssh_host, shell=True,
                   stdout=open('/dev/null', 'w')) != 0:
            time.sleep(5)
        time.sleep(self.EXTRA_SLEEP)
        print 'Trying to SSH into VM'
        subprocess.check_call(('scp', t.name, ssh_host+':build-calibre'))
        subprocess.check_call(self.BUILD_CMD%ssh_host, shell=True)

    def installer(self):
        return installer_name(self.INSTALLER_EXT, self.IS_64_BIT)

    def run(self, opts):
        for x in ('dont_shutdown', 'vm'):
            setattr(self, x, getattr(opts, x))
        if self.vm is None:
            self.vm = self.VM
        if not self.vmware_started():
            self.start_vmware()
        subprocess.call(['chmod', '-R', '+r', 'resources/recipes'])
        self.start_vm()
        self.download_installer()
        if not self.dont_shutdown:
            subprocess.call(['ssh', self.VM_NAME]+self.SHUTDOWN_CMD)

    def download_installer(self):
        installer = self.installer()
        subprocess.check_call(['scp',
            self.VM_NAME+':build/calibre/'+installer, 'dist'])
        if not os.path.exists(installer):
            self.warn('Failed to download installer')
            raise SystemExit(1)

    def clean(self):
        installer = self.installer()
        if os.path.exists(installer):
            os.remove(installer)
