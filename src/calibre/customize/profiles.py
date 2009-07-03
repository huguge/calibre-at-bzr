from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from itertools import izip

from calibre.customize import Plugin as _Plugin

FONT_SIZES = [('xx-small', 1),
              ('x-small',  None),
              ('small',    2),
              ('medium',   3),
              ('large',    4),
              ('x-large',  5),
              ('xx-large', 6),
              (None,       7)]


class Plugin(_Plugin):

    fbase  = 12
    fsizes = [5, 7, 9, 12, 13.5, 17, 20, 22, 24]
    screen_size = (1600, 1200)
    dpi = 100

    def __init__(self, *args, **kwargs):
        _Plugin.__init__(self, *args, **kwargs)
        self.width, self.height = self.screen_size
        fsizes = list(self.fsizes)
        self.fkey = list(self.fsizes)
        self.fsizes = []
        for (name, num), size in izip(FONT_SIZES, fsizes):
            self.fsizes.append((name, num, float(size)))
        self.fnames = dict((name, sz) for name, _, sz in self.fsizes if name)
        self.fnums = dict((num, sz) for _, num, sz in self.fsizes if num)


class InputProfile(Plugin):

    author = 'Kovid Goyal'
    supported_platforms = set(['windows', 'osx', 'linux'])
    can_be_disabled = False
    type = _('Input profile')

    name        = 'Default Input Profile'
    short_name  = 'default' # Used in the CLI so dont use spaces etc. in it
    description = _('This profile tries to provide sane defaults and is useful '
                    'if you know nothing about the input document.')


class SonyReaderInput(InputProfile):

    name        = 'Sony Reader'
    short_name  = 'sony'
    description = _('This profile is intended for the SONY PRS line. '
                    'The 500/505/700 etc.')

    screen_size               = (584, 754)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]


class MSReaderInput(InputProfile):

    name        = 'Microsoft Reader'
    short_name  = 'msreader'
    description = _('This profile is intended for the Microsoft Reader.')

    screen_size               = (480, 652)
    dpi                       = 96
    fbase                     = 13
    fsizes                    = [10, 11, 13, 16, 18, 20, 22, 26]

class MobipocketInput(InputProfile):

    name        = 'Mobipocket Books'
    short_name  = 'mobipocket'
    description = _('This profile is intended for the Mobipocket books.')

    # Unfortunately MOBI books are not narrowly targeted, so this information is
    # quite likely to be spurious
    screen_size               = (600, 800)
    dpi                       = 96
    fbase                     = 18
    fsizes                    = [14, 14, 16, 18, 20, 22, 24, 26]

class HanlinV3Input(InputProfile):

    name        = 'Hanlin V3'
    short_name  = 'hanlinv3'
    description = _('This profile is intended for the Hanlin V3 and its clones.')

    # Screen size is a best guess
    screen_size               = (584, 754)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class CybookG3Input(InputProfile):

    name        = 'Cybook G3'
    short_name  = 'cybookg3'
    description = _('This profile is intended for the Cybook G3.')

    # Screen size is a best guess
    screen_size               = (600, 800)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class KindleInput(InputProfile):

    name        = 'Kindle'
    short_name  = 'kindle'
    description = _('This profile is intended for the Amazon Kindle.')

    # Screen size is a best guess
    screen_size               = (525, 640)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]


input_profiles = [InputProfile, SonyReaderInput, MSReaderInput,
        MobipocketInput, HanlinV3Input, CybookG3Input, KindleInput]


class OutputProfile(Plugin):

    author = 'Kovid Goyal'
    supported_platforms = set(['windows', 'osx', 'linux'])
    can_be_disabled = False
    type = _('Output profile')

    name        = 'Default Output Profile'
    short_name  = 'default' # Used in the CLI so dont use spaces etc. in it
    description = _('This profile tries to provide sane defaults and is useful '
                    'if you want to produce a document intended to be read at a '
                    'computer or on a range of devices.')

    # The image size for comics
    comic_screen_size = (584, 754)

    @classmethod
    def tags_to_string(cls, tags):
        return ', '.join(tags)

class SonyReaderOutput(OutputProfile):

    name        = 'Sony Reader'
    short_name  = 'sony'
    description = _('This profile is intended for the SONY PRS line. '
                    'The 500/505/700 etc.')

    screen_size               = (600, 775)
    dpi                       = 168.451
    fbase                     = 12
    fsizes                    = [7.5, 9, 10, 12, 15.5, 20, 22, 24]

class SonyReaderLandscapeOutput(SonyReaderOutput):

    name        = 'Sony Reader Landscape'
    short_name  = 'sony-landscape'
    description = _('This profile is intended for the SONY PRS line. '
                    'The 500/505/700 etc, in landscape mode. Mainly useful '
                    'for comics.')

    screen_size               = (784, 1012)
    comic_screen_size         = (784, 1012)


class MSReaderOutput(OutputProfile):

    name        = 'Microsoft Reader'
    short_name  = 'msreader'
    description = _('This profile is intended for the Microsoft Reader.')

    screen_size               = (480, 652)
    dpi                       = 96
    fbase                     = 13
    fsizes                    = [10, 11, 13, 16, 18, 20, 22, 26]

class MobipocketOutput(OutputProfile):

    name        = 'Mobipocket Books'
    short_name  = 'mobipocket'
    description = _('This profile is intended for the Mobipocket books.')

    # Unfortunately MOBI books are not narrowly targeted, so this information is
    # quite likely to be spurious
    screen_size               = (600, 800)
    dpi                       = 96
    fbase                     = 18
    fsizes                    = [14, 14, 16, 18, 20, 22, 24, 26]

class HanlinV3Output(OutputProfile):

    name        = 'Hanlin V3'
    short_name  = 'hanlinv3'
    description = _('This profile is intended for the Hanlin V3 and its clones.')

    # Screen size is a best guess
    screen_size               = (584, 754)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class CybookG3Output(OutputProfile):

    name        = 'Cybook G3'
    short_name  = 'cybookg3'
    description = _('This profile is intended for the Cybook G3.')

    # Screen size is a best guess
    screen_size               = (600, 800)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

class KindleOutput(OutputProfile):

    name        = 'Kindle'
    short_name  = 'kindle'
    description = _('This profile is intended for the Amazon Kindle.')

    # Screen size is a best guess
    screen_size               = (525, 640)
    dpi                       = 168.451
    fbase                     = 16
    fsizes                    = [12, 12, 14, 16, 18, 20, 22, 24]

    @classmethod
    def tags_to_string(cls, tags):
        return 'ttt '.join(tags)+'ttt '

class KindleDXOutput(OutputProfile):

    name        = 'Kindle DX'
    short_name  = 'kindle_dx'
    description = _('This profile is intended for the Amazon Kindle DX.')

    # Screen size is a best guess
    screen_size               = (744, 1022)
    dpi                       = 150.0
    comic_screen_size         = (741, 1022)

    @classmethod
    def tags_to_string(cls, tags):
        return 'ttt '.join(tags)+'ttt '


output_profiles = [OutputProfile, SonyReaderOutput, MSReaderOutput,
        MobipocketOutput, HanlinV3Output, CybookG3Output, KindleOutput,
        SonyReaderLandscapeOutput, KindleDXOutput]
