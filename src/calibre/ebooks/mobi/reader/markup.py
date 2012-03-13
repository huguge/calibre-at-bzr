#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os

def update_internal_links(mobi8_reader):
    # need to update all links that are internal which
    # are based on positions within the xhtml files **BEFORE**
    # cutting and pasting any pieces into the xhtml text files

    #   kindle:pos:fid:XXXX:off:YYYYYYYYYY  (used for internal link within xhtml)
    #       XXXX is the offset in records into divtbl
    #       YYYYYYYYYYYY is a base32 number you add to the divtbl insertpos to get final position

    mr = mobi8_reader

    # pos:fid pattern
    posfid_pattern = re.compile(br'''(<a.*?href=.*?>)''', re.IGNORECASE)
    posfid_index_pattern = re.compile(br'''['"]kindle:pos:fid:([0-9|A-V]+):off:([0-9|A-V]+).*?["']''')

    parts = []
    for part in mr.parts:
        srcpieces = posfid_pattern.split(part)
        for j in xrange(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag.startswith(b'<'):
                for m in posfid_index_pattern.finditer(tag):
                    posfid = m.group(1)
                    offset = m.group(2)
                    filename, idtag = mr.get_id_tag_by_pos_fid(posfid, offset)
                    suffix = (b'#' + idtag) if idtag else b''
                    replacement = filename.encode(mr.header.codec) + suffix
                    tag = posfid_index_pattern.sub(replacement, tag, 1)
                srcpieces[j] = tag
        part = ''.join([x.decode(mr.header.codec) for x in srcpieces])
        parts.append(part)

    # All parts are now unicode and have no internal links
    return parts

def remove_kindlegen_markup(parts):

    # we can safely remove all of the Kindlegen generated aid tags
    find_tag_with_aid_pattern = re.compile(r'''(<[^>]*\said\s*=[^>]*>)''',
            re.IGNORECASE)
    within_tag_aid_position_pattern = re.compile(r'''\said\s*=['"][^'"]*['"]''')

    for i in xrange(len(parts)):
        part = parts[i]
        srcpieces = find_tag_with_aid_pattern.split(part)
        for j in range(len(srcpieces)):
            tag = srcpieces[j]
            if tag.startswith('<'):
                for m in within_tag_aid_position_pattern.finditer(tag):
                    replacement = ''
                    tag = within_tag_aid_position_pattern.sub(replacement, tag,
                            1)
                srcpieces[j] = tag
        part = "".join(srcpieces)
        parts[i] = part

    # we can safely remove all of the Kindlegen generated data-AmznPageBreak tags
    find_tag_with_AmznPageBreak_pattern = re.compile(
            r'''(<[^>]*\sdata-AmznPageBreak=[^>]*>)''', re.IGNORECASE)
    within_tag_AmznPageBreak_position_pattern = re.compile(
            r'''\sdata-AmznPageBreak=['"][^'"]*['"]''')

    for i in xrange(len(parts)):
        part = parts[i]
        srcpieces = find_tag_with_AmznPageBreak_pattern.split(part)
        for j in range(len(srcpieces)):
            tag = srcpieces[j]
            if tag.startswith('<'):
                for m in within_tag_AmznPageBreak_position_pattern.finditer(tag):
                    replacement = ''
                    tag = within_tag_AmznPageBreak_position_pattern.sub(replacement, tag, 1)
                srcpieces[j] = tag
        part = "".join(srcpieces)
        parts[i] = part

def update_flow_links(mobi8_reader, resource_map, log):
    #   kindle:embed:XXXX?mime=image/gif (png, jpeg, etc) (used for images)
    #   kindle:flow:XXXX?mime=YYYY/ZZZ (used for style sheets, svg images, etc)
    #   kindle:embed:XXXX   (used for fonts)

    mr = mobi8_reader
    flows = []

    img_pattern = re.compile(r'''(<[img\s|image\s][^>]*>)''', re.IGNORECASE)
    img_index_pattern = re.compile(r'''['"]kindle:embed:([0-9|A-V]+)[^'"]*['"]''', re.IGNORECASE)

    tag_pattern = re.compile(r'''(<[^>]*>)''')
    flow_pattern = re.compile(r'''['"]kindle:flow:([0-9|A-V]+)\?mime=([^'"]+)['"]''', re.IGNORECASE)

    url_pattern = re.compile(r'''(url\(.*?\))''', re.IGNORECASE)
    url_img_index_pattern = re.compile(r'''kindle:embed:([0-9|A-V]+)\?mime=image/[^\)]*''', re.IGNORECASE)
    font_index_pattern = re.compile(r'''kindle:embed:([0-9|A-V]+)''', re.IGNORECASE)
    url_css_index_pattern = re.compile(r'''kindle:flow:([0-9|A-V]+)\?mime=text/css[^\)]*''', re.IGNORECASE)

    for flow in mr.flows:
        if flow is None: # 0th flow is None
            flows.append(flow)
            continue

        if not isinstance(flow, unicode):
            flow = flow.decode(mr.header.codec)

        # links to raster image files from image tags
        # image_pattern
        srcpieces = img_pattern.split(flow)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag.startswith('<im'):
                for m in img_index_pattern.finditer(tag):
                    num = int(m.group(1), 32)
                    href = resource_map[num-1]
                    if href:
                        replacement = '"%s"'%('../'+ href)
                        tag = img_index_pattern.sub(replacement, tag, 1)
                    else:
                        log.warn('Referenced image %s was not recognized '
                                'as a valid image in %s' % (num, tag))
                srcpieces[j] = tag
        flow = "".join(srcpieces)

        # replacements inside css url():
        srcpieces = url_pattern.split(flow)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]

            # process links to raster image files
            for m in url_img_index_pattern.finditer(tag):
                num = int(m.group(1), 32)
                href = resource_map[num-1]
                if href:
                    replacement = '"%s"'%('../'+ href)
                    tag = url_img_index_pattern.sub(replacement, tag, 1)
                else:
                    log.warn('Referenced image %s was not recognized as a '
                    'valid image in %s' % (num, tag))

            # process links to fonts
            for m in font_index_pattern.finditer(tag):
                num = int(m.group(1), 32)
                href = resource_map[num-1]
                if href is None:
                    log.warn('Referenced font %s was not recognized as a '
                    'valid font in %s' % (num, tag))
                else:
                    replacement = '"%s"'%('../'+ href)
                    if href.endswith('.failed'):
                        replacement = '"%s"'%('failed-'+href)
                    tag = font_index_pattern.sub(replacement, tag, 1)

            # process links to other css pieces
            for m in url_css_index_pattern.finditer(tag):
                num = int(m.group(1), 32)
                fi = mr.flowinfo[num]
                replacement = '"../' + fi.dir + '/' + fi.fname + '"'
                tag = url_css_index_pattern.sub(replacement, tag, 1)

            srcpieces[j] = tag
        flow = "".join(srcpieces)

        # flow pattern not inside url()
        srcpieces = re.split(tag_pattern, flow)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag.startswith('<'):
                for m in re.finditer(flow_pattern, tag):
                    num = int(m.group(1), 32)
                    fi = mr.flowinfo[num]
                    if fi.format == 'inline':
                        flowtext = mr.flows[num]
                        tag = flowtext
                    else:
                        replacement = '"../' + fi.dir + '/' + fi.fname + '"'
                        tag = flow_pattern.sub(replacement, tag, 1)
                srcpieces[j] = tag
        flow = "".join(srcpieces)

        flows.append(flow)

    # All flows are now unicode and have links resolved
    return flows

def insert_flows_into_markup(parts, flows, mobi8_reader):
    mr = mobi8_reader

    # kindle:flow:XXXX?mime=YYYY/ZZZ (used for style sheets, svg images, etc)
    tag_pattern = re.compile(r'''(<[^>]*>)''')
    flow_pattern = re.compile(r'''['"]kindle:flow:([0-9|A-V]+)\?mime=([^'"]+)['"]''', re.IGNORECASE)
    for i in xrange(len(parts)):
        part = parts[i]

        # flow pattern
        srcpieces = tag_pattern.split(part)
        for j in range(1, len(srcpieces),2):
            tag = srcpieces[j]
            if tag.startswith('<'):
                for m in flow_pattern.finditer(tag):
                    num = int(m.group(1), 32)
                    fi = mr.flowinfo[num]
                    if fi.format == 'inline':
                        tag = flows[num]
                    else:
                        replacement = '"../' + fi.dir + '/' + fi.fname + '"'
                        tag = flow_pattern.sub(replacement, tag, 1)
                srcpieces[j] = tag
        part = "".join(srcpieces)
        # store away modified version
        parts[i] = part

def insert_images_into_markup(parts, resource_map, log):
    # Handle any embedded raster images links in the xhtml text
    # kindle:embed:XXXX?mime=image/gif (png, jpeg, etc) (used for images)
    img_pattern = re.compile(r'''(<[img\s|image\s][^>]*>)''', re.IGNORECASE)
    img_index_pattern = re.compile(r'''['"]kindle:embed:([0-9|A-V]+)[^'"]*['"]''')
    for i in xrange(len(parts)):
        part = parts[i]
        #[partnum, dir, filename, beg, end, aidtext] = self.k8proc.partinfo[i]

        # links to raster image files
        # image_pattern
        srcpieces = img_pattern.split(part)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag.startswith('<im'):
                for m in img_index_pattern.finditer(tag):
                    num = int(m.group(1), 32)
                    href = resource_map[num-1]
                    if href:
                        replacement = '"%s"'%('../' + href)
                        tag = img_index_pattern.sub(replacement, tag, 1)
                    else:
                        log.warn('Referenced image %s was not recognized as '
                                'a valid image in %s' % (num, tag))
                srcpieces[j] = tag
        part = "".join(srcpieces)
        # store away modified version
        parts[i] = part

def upshift_markup(parts):
    tag_pattern = re.compile(r'''(<(?:svg)[^>]*>)''', re.IGNORECASE)

    for i in xrange(len(parts)):
        part = parts[i]

        # tag pattern
        srcpieces = re.split(tag_pattern, part)
        for j in range(1, len(srcpieces), 2):
            tag = srcpieces[j]
            if tag[:4].lower() == '<svg':
                tag = tag.replace('preserveaspectratio','preserveAspectRatio')
                tag = tag.replace('viewbox','viewBox')
            srcpieces[j] = tag
        part = "".join(srcpieces)
        # store away modified version
        parts[i] = part

def expand_mobi8_markup(mobi8_reader, resource_map, log):
    # First update all internal links that are based on offsets
    parts = update_internal_links(mobi8_reader)

    # Remove pointless markup inserted by kindlegen
    remove_kindlegen_markup(parts)

    # Handle substitutions for the flows pieces first as they may
    # be inlined into the xhtml text
    flows = update_flow_links(mobi8_reader, resource_map, log)

    # Insert inline flows into the markup
    insert_flows_into_markup(parts, flows, mobi8_reader)

    # Insert raster images into markup
    insert_images_into_markup(parts, resource_map, log)

    # Perform general markup cleanups
    upshift_markup(parts)

    # Update the parts and flows stored in the reader
    mobi8_reader.parts = parts
    mobi8_reader.flows = flows

    # write out the parts and file flows
    os.mkdir('text') # directory containing all parts
    spine = []
    for i, part in enumerate(parts):
        pi = mobi8_reader.partinfo[i]
        with open(os.path.join(pi.type, pi.filename), 'wb') as f:
            f.write(part.encode('utf-8'))
            spine.append(f.name)

    for i, flow in enumerate(flows):
        fi = mobi8_reader.flowinfo[i]
        if fi.format == 'file':
            if not os.path.exists(fi.dir):
                os.mkdir(fi.dir)
            with open(os.path.join(fi.dir, fi.fname), 'wb') as f:
                f.write(flow.encode('utf-8'))

    return spine

