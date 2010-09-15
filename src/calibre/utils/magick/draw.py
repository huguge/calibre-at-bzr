#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.utils.magick import Image, DrawingWand, create_canvas
from calibre.constants import __appname__, __version__
from calibre import fit_image

def save_cover_data_to(data, path, bgcolor='white', resize_to=None,
        return_data=False):
    '''
    Saves image in data to path, in the format specified by the path
    extension. Composes the image onto a blank canvas so as to
    properly convert transparent images.
    '''
    img = Image()
    img.load(data)
    if resize_to is not None:
        img.size = (resize_to[0], resize_to[1])
    canvas = create_canvas(img.size[0], img.size[1], bgcolor)
    canvas.compose(img)
    if return_data:
        return canvas.export(os.path.splitext(path)[1][1:])
    canvas.save(path)

def thumbnail(data, width=120, height=120, bgcolor='white', fmt='jpg'):
    img = Image()
    img.load(data)
    owidth, oheight = img.size
    scaled, nwidth, nheight = fit_image(owidth, oheight, width, height)
    if scaled:
        img.size = (nwidth, nheight)
    canvas = create_canvas(img.size[0], img.size[1], bgcolor)
    canvas.compose(img)
    return (canvas.size[0], canvas.size[1], canvas.export(fmt))

def identify_data(data):
    '''
    Identify the image in data. Returns a 3-tuple
    (width, height, format)
    or raises an Exception if data is not an image.
    '''
    img = Image()
    img.load(data)
    width, height = img.size
    fmt = img.format
    return (width, height, fmt)

def identify(path):
    '''
    Identify the image at path. Returns a 3-tuple
    (width, height, format)
    or raises an Exception.
    '''
    data = open(path, 'rb').read()
    return identify_data(data)

def add_borders_to_image(path_to_image, left=0, top=0, right=0, bottom=0,
        border_color='white'):
    img = Image()
    img.open(path_to_image)
    lwidth, lheight = img.size
    canvas = create_canvas(lwidth+left+right, lheight+top+bottom,
                border_color)
    canvas.compose(img, left, top)
    canvas.save(path_to_image)

def create_text_wand(font_size, font_path=None):
    if font_path is None:
        font_path = P('fonts/liberation/LiberationSerif-Bold.ttf')
    ans = DrawingWand()
    ans.font = font_path
    ans.font_size = font_size
    ans.gravity = 'CenterGravity'
    ans.text_alias = True
    return ans

def create_text_arc(text, font_size, font=None, bgcolor='white'):
    if isinstance(text, unicode):
        text = text.encode('utf-8')

    canvas = create_canvas(300, 300, bgcolor)

    tw = create_text_wand(font_size, font_path=font)
    m = canvas.font_metrics(tw, text)
    canvas = create_canvas(int(m.text_width)+20, int(m.text_height*3.5), bgcolor)
    canvas.annotate(tw, 0, 0, 0, text)
    canvas.distort("ArcDistortion", [120], True)
    canvas.trim(0)
    return canvas

def _get_line(img, dw, tokens, line_width):
    line, rest = tokens, []
    while True:
        m = img.font_metrics(dw, ' '.join(line))
        width, height = m.text_width, m.text_height
        if width < line_width:
            return line, rest
        rest = line[-1:] + rest
        line = line[:-1]

def annotate_img(img, dw, left, top, rotate, text,
        translate_from_top_left=True):
    if isinstance(text, unicode):
        text = text.encode('utf-8')
    if translate_from_top_left:
        m = img.font_metrics(dw, text)
        img_width, img_height = img.size
        left = left - img_width/2. + m.text_width/2.
        top  = top - img_height/2. + m.text_height/2.
    img.annotate(dw, left, top, rotate, text)

def draw_centered_line(img, dw, line, top):
    m = img.font_metrics(dw, line)
    width, height = m.text_width, m.text_height
    img_width = img.size[0]
    left = max(int((img_width - width)/2.), 0)
    annotate_img(img, dw, left, top, 0, line)
    return top + height

def draw_centered_text(img, dw, text, top, margin=10):
    img_width = img.size[0]
    tokens = text.split(' ')
    while tokens:
        line, tokens = _get_line(img, dw, tokens, img_width-2*margin)
        if not line:
            # Could not fit the first token on the line
            line = tokens[:1]
            tokens = tokens[1:]
        bottom = draw_centered_line(img, dw, ' '.join(line), top)
        top = bottom
    return top

class TextLine(object):

    def __init__(self, text, font_size, bottom_margin=30, font_path=None):
        self.text, self.font_size, = text, font_size
        self.bottom_margin = bottom_margin
        self.font_path = font_path

    def __repr__(self):
        return u'TextLine:%r:%f'%(self.text, self.font_size)


def create_cover_page(top_lines, logo_path, width=590, height=750,
        bgcolor='white', output_format='jpg'):
    '''
    Create the standard calibre cover page and return it as a byte string in
    the specified output_format.
    '''
    canvas = create_canvas(width, height, bgcolor)

    bottom = 10
    for line in top_lines:
        twand = create_text_wand(line.font_size, font_path=line.font_path)
        bottom = draw_centered_text(canvas, twand, line.text, bottom)
        bottom += line.bottom_margin
    bottom -= top_lines[-1].bottom_margin

    vanity = create_text_arc(__appname__ + ' ' + __version__, 24,
            font=P('fonts/liberation/LiberationMono-Regular.ttf'))
    lwidth, lheight = vanity.size
    left = int(max(0, (width - lwidth)/2.))
    top  = height - lheight - 10
    canvas.compose(vanity, left, top)

    available = (width, int(top - bottom)-20)
    if available[1] > 40:
        logo = Image()
        logo.open(logo_path)
        lwidth, lheight = logo.size
        scaled, lwidth, lheight = fit_image(lwidth, lheight, *available)
        if scaled:
            logo.size = (lwidth, lheight)
        left = int(max(0, (width - lwidth)/2.))
        top  = bottom+10
        canvas.compose(logo, left, top)

    return canvas.export(output_format)

