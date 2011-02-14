#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, cPickle, re, anydbm, shutil
from zlib import compress

from setup import Command, basenames, __appname__

def get_opts_from_parser(parser):
    def do_opt(opt):
        for x in opt._long_opts:
            yield x
        for x in opt._short_opts:
            yield x
    for o in parser.option_list:
        for x in do_opt(o): yield x
    for g in parser.option_groups:
        for o in g.option_list:
            for x in do_opt(o): yield x

class Resources(Command):

    description = 'Compile various needed calibre resources'

    KAKASI_PATH = os.path.join(Command.SRC,  __appname__,
            'ebooks', 'unihandecode', 'pykakasi')

    def run(self, opts):
        scripts = {}
        for x in ('console', 'gui'):
            for name in basenames[x]:
                if name in ('calibre-complete', 'calibre_postinstall'):
                    continue
                scripts[name] = x

        dest = self.j(self.RESOURCES, 'scripts.pickle')
        if self.newer(dest, self.j(self.SRC, 'calibre', 'linux.py')):
            self.info('\tCreating scripts.pickle')
            f = open(dest, 'wb')
            cPickle.dump(scripts, f, -1)

        from calibre.web.feeds.recipes.collection import \
                serialize_builtin_recipes, iterate_over_builtin_recipe_files

        files = [x[1] for x in iterate_over_builtin_recipe_files()]

        dest = self.j(self.RESOURCES, 'builtin_recipes.xml')
        if self.newer(dest, files):
            self.info('\tCreating builtin_recipes.xml')
            xml = serialize_builtin_recipes()
            with open(dest, 'wb') as f:
                f.write(xml)

        dest = self.j(self.RESOURCES, 'ebook-convert-complete.pickle')
        files = []
        for x in os.walk(self.j(self.SRC, 'calibre')):
            for f in x[-1]:
                if f.endswith('.py'):
                    files.append(self.j(x[0], f))
        if self.newer(dest, files):
            self.info('\tCreating ebook-convert-complete.pickle')
            complete = {}
            from calibre.ebooks.conversion.plumber import supported_input_formats
            complete['input_fmts'] = set(supported_input_formats())
            from calibre.web.feeds.recipes.collection import get_builtin_recipe_titles
            complete['input_recipes'] = [t+'.recipe ' for t in
                    get_builtin_recipe_titles()]
            from calibre.customize.ui import available_output_formats
            complete['output'] = set(available_output_formats())
            from calibre.ebooks.conversion.cli import create_option_parser
            from calibre.utils.logging import Log
            log = Log()
            #log.outputs = []
            for inf in supported_input_formats():
                if inf in ('zip', 'rar', 'oebzip'):
                    continue
                for ouf in available_output_formats():
                    of = ouf if ouf == 'oeb' else 'dummy.'+ouf
                    p = create_option_parser(('ec', 'dummy1.'+inf, of, '-h'),
                            log)[0]
                    complete[(inf, ouf)] = [x+' 'for x in
                            get_opts_from_parser(p)]

            cPickle.dump(complete, open(dest, 'wb'), -1)

        self.info('\tCreating template-functions.json')
        dest = self.j(self.RESOURCES, 'template-functions.json')
        function_dict = {}
        import inspect
        from calibre.utils.formatter_functions import all_builtin_functions
        for obj in all_builtin_functions:
            eval_func = inspect.getmembers(obj,
                    lambda x: inspect.ismethod(x) and x.__name__ == 'evaluate')
            try:
                lines = [l[4:] for l in inspect.getsourcelines(eval_func[0][1])[0]]
            except:
                continue
            lines = ''.join(lines)
            function_dict[obj.name] = lines
        import json
        json.dump(function_dict, open(dest, 'wb'), indent=4)

        self.run_kakasi(opts)

    def run_kakasi(self, opts):
        self.records = {}
        src = self.j(self.KAKASI_PATH, 'kakasidict.utf8')
        dest = self.j(self.RESOURCES, 'localization',
                'pykakasi','kanwadict2.db')
        base = os.path.dirname(dest)
        if not os.path.exists(base):
            os.makedirs(base)

        if not self.newer(dest, src):
            self.info('\tKanwadict is up to date')
        else:
            self.info('\tGenerating Kanwadict')

            for line in open(src, "r"):
                self.parsekdict(line)
            self.kanwaout(dest)

        src = self.j(self.KAKASI_PATH, 'itaijidict.utf8')
        dest = self.j(self.RESOURCES, 'localization',
                'pykakasi','itaijidict2.pickle')

        if not self.newer(dest, src):
            self.info('\tItaijidict is up to date')
        else:
            self.info('\tGenerating Itaijidict')
            self.mkitaiji(src, dest)

        src = self.j(self.KAKASI_PATH, 'kanadict.utf8')
        dest = self.j(self.RESOURCES, 'localization',
                'pykakasi','kanadict2.pickle')

        if not self.newer(dest, src):
            self.info('\tKanadict is up to date')
        else:
            self.info('\tGenerating kanadict')
            self.mkkanadict(src, dest)

        return


    def mkitaiji(self, src, dst):
        dic = {}
        for line in open(src, "r"):
            line = line.decode("utf-8").strip()
            if line.startswith(';;'): # skip comment
                continue
            if re.match(r"^$",line):
                continue
            pair = re.sub(r'\\u([0-9a-fA-F]{4})', lambda x:unichr(int(x.group(1),16)), line)
            dic[pair[0]] = pair[1]
        cPickle.dump(dic, open(dst, 'w'), protocol=-1) #pickle

    def mkkanadict(self, src, dst):
        dic = {}
        for line in open(src, "r"):
            line = line.decode("utf-8").strip()
            if line.startswith(';;'): # skip comment
                continue
            if re.match(r"^$",line):
                continue
            (alpha, kana) = line.split(' ')
            dic[kana] = alpha
        cPickle.dump(dic, open(dst, 'w'), protocol=-1) #pickle

    def parsekdict(self, line):
        line = line.decode("utf-8").strip()
        if line.startswith(';;'): # skip comment
            return
        (yomi, kanji) = line.split(' ')
        if ord(yomi[-1:]) <= ord('z'):
            tail = yomi[-1:]
            yomi = yomi[:-1]
        else:
            tail = ''
        self.updaterec(kanji, yomi, tail)

    def updaterec(self, kanji, yomi, tail):
            key = "%04x"%ord(kanji[0])
            if key in self.records:
                if kanji in self.records[key]:
                    rec = self.records[key][kanji]
                    rec.append((yomi,tail))
                    self.records[key].update( {kanji: rec} )
                else:
                    self.records[key][kanji]=[(yomi, tail)]
            else:
                self.records[key] = {}
                self.records[key][kanji]=[(yomi, tail)]

    def kanwaout(self, out):
        dic = anydbm.open(out, 'c')
        for (k, v) in self.records.iteritems():
            dic[k] = compress(cPickle.dumps(v, -1))
        dic.close()


    def clean(self):
        for x in ('scripts', 'recipes', 'ebook-convert-complete'):
            x = self.j(self.RESOURCES, x+'.pickle')
            if os.path.exists(x):
                os.remove(x)
        kakasi = self.j(self.RESOURCES, 'localization', 'pykakasi')
        if os.path.exists(kakasi):
            shutil.rmtree(kakasi)




