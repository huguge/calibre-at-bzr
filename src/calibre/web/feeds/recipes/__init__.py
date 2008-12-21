#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Builtin recipes.
'''
recipe_modules = [
           'newsweek', 'atlantic', 'economist', 'portfolio',
           'nytimes', 'usatoday', 'outlook_india', 'bbc', 'greader', 'wsj',
           'wired', 'globe_and_mail', 'smh', 'espn', 'business_week',
           'ars_technica', 'upi', 'new_yorker', 'irish_times', 'iht', 'lanacion',
           'discover_magazine', 'scientific_american', 'new_york_review_of_books',
           'daily_telegraph', 'guardian', 'el_pais', 'new_scientist', 'b92',
           'politika', 'moscow_times', 'latimes', 'japan_times', 'san_fran_chronicle',
           'demorgen_be', 'de_standaard', 'ap', 'barrons', 'chr_mon', 'cnn', 'faznet',
           'jpost', 'jutarnji', 'nasa', 'reuters', 'spiegelde', 'wash_post', 'zeitde',
           'blic', 'novosti', 'danas', 'vreme', 'times_online', 'the_scotsman',
           'nytimes_sub', 'security_watch', 'cyberpresse', 'st_petersburg_times',
           'clarin', 'financial_times', 'heise', 'le_monde', 'harpers', 'science_aas',
           'science_news', 'the_nation', 'lrb', 'harpers_full', 'liberation',
           'linux_magazine', 'telegraph_uk', 'utne', 'sciencedaily'
          ]

import re, imp, inspect, time, os
from calibre.web.feeds.news import BasicNewsRecipe, CustomIndexRecipe, AutomaticNewsRecipe
from calibre.ebooks.lrf.web.profiles import DefaultProfile, FullContentProfile
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.path import path
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre import __appname__, english_sort

basic_recipes = (BasicNewsRecipe, AutomaticNewsRecipe, CustomIndexRecipe, DefaultProfile, FullContentProfile)
basic_recipe_names = (i.__name__ for i in basic_recipes)


#: Compile builtin recipe/profile classes
def load_recipe(module, package='calibre.web.feeds.recipes'):
    module = __import__(package+'.'+module, fromlist=[''])
    for attr in dir(module):
        obj = getattr(module, attr)
        if type(obj) is not type:
            continue
        recipe = False
        for b in obj.__bases__:
            if b in basic_recipes:
                recipe = True
                break
        if not recipe:
            continue
        if obj not in basic_recipes:
            return obj


recipes = [load_recipe(i) for i in recipe_modules]

_tdir = None
_crep = 0
def compile_recipe(src):
    '''
    Compile the code in src and return the first object that is a recipe or profile.
    @param src: Python source code
    @type src: string
    @return: Recipe/Profile class or None, if no such class was found in C{src}
    '''
    global _tdir, _crep
    if _tdir is None or not os.path.exists(_tdir):
        _tdir = path(PersistentTemporaryDirectory('_recipes'))
    temp = _tdir/('recipe%d.py'%_crep)
    _crep += 1
    if not isinstance(src, unicode):
        match = re.search(r'coding[:=]\s*([-\w.]+)', src[:200])
        enc = match.group(1) if match else 'utf-8'
        src = src.decode(enc)
    f = open(temp, 'wb')
    src = 'from %s.web.feeds.news import BasicNewsRecipe, AutomaticNewsRecipe\n'%__appname__ + src
    src = 'from %s.ebooks.lrf.web.profiles import DefaultProfile, FullContentProfile\n'%__appname__ + src
    src = '# coding: utf-8\n' + src
    f.write(src.replace('from libprs500', 'from calibre').encode('utf-8'))
    f.close()
    module = imp.find_module(temp.namebase, [temp.dirname()])
    module = imp.load_module(temp.namebase, *module)
    classes = inspect.getmembers(module,
            lambda x : inspect.isclass(x) and \
                issubclass(x, (DefaultProfile, BasicNewsRecipe)) and \
                x not in basic_recipes)
    if not classes:
        return None

    return classes[0][1]


def get_builtin_recipe(title):
    '''
    Return a builtin recipe/profile class whose title == C{title} or None if no such
    recipe exists. Also returns a flag that is True iff the found recipe is really
    an old-style Profile.

    @type title: string
    @rtype: class or None, boolean
    '''
    for r in recipes:
        if r.title == title:
            return r
    return None

_titles = [r.title for r in recipes]
_titles.sort(cmp=english_sort)
titles = _titles

def migrate_automatic_profile_to_automatic_recipe(profile):
    oprofile = profile
    profile = compile_recipe(profile)
    if 'BasicUserProfile' not in profile.__name__:
        return oprofile
    return '''\
class BasicUserRecipe%d(AutomaticNewsRecipe):

    title = %s
    oldest_article = %d
    max_articles_per_feed = %d
    summary_length = %d

    feeds = %s

'''%(int(time.time()), repr(profile.title), profile.oldest_article,
    profile.max_articles_per_feed, profile.summary_length, repr(profile.feeds))

