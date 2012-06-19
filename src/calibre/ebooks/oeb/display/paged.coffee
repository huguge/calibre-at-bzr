#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2012, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

log = (args...) -> # {{{
    if args
        msg = args.join(' ')
        if window?.console?.log
            window.console.log(msg)
        else if process?.stdout?.write
            process.stdout.write(msg + '\n')
# }}}

body_height = () ->
    db = document.body
    dde = document.documentElement
    if db? and dde?
        return Math.max(db.scrollHeight, dde.scrollHeight, db.offsetHeight,
            dde.offsetHeight, db.clientHeight, dde.clientHeight)
    return 0

absleft = (elem) ->
    r = elem.getBoundingClientRect()
    return r.left + window.pageXOffset

class PagedDisplay
    ###
    This class is a namespace to expose functions via the
    window.paged_display object. The most important functions are:

    layout(): causes the currently loaded document to be laid out in columns.
    ###

    constructor: () ->
        this.set_geometry()
        this.page_width = 0
        this.screen_width = 0
        this.in_paged_mode = false
        this.current_margin_side = 0

    set_geometry: (cols_per_screen=2, margin_top=20, margin_side=40, margin_bottom=20) ->
        this.margin_top = margin_top
        this.margin_side = margin_side
        this.margin_bottom = margin_bottom
        this.cols_per_screen = cols_per_screen

    layout: () ->
        ww = window.innerWidth
        wh = window.innerHeight
        body_height = wh - this.margin_bottom = this.margin_top
        n = this.cols_per_screen

        # Calculate the column width so that cols_per_screen columns fit in the
        # window in such a way the right margin of the last column is <=
        # side_margin (it may be less if the window width is not a
        # multiple of n*(col_width+2*side_margin).

        adjust = ww - Math.floor(ww/n)*n
        # Ensure that the margins are large enough that the adjustment does not
        # cause them to become negative semidefinite
        sm = Math.max(2*adjust, this.margin_side)
        # Minimum column width, for the cases when the window is too
        # narrow
        col_width = Math.max(100, ((ww - adjust)/n) - 2*sm)
        this.page_width = col_width + 2*sm
        this.screen_width = this.page_width * this.cols_per_screen

        body_style = window.getComputedStyle(document.body)
        fgcolor = body_style.getPropertyValue('color')
        bs = document.body.style

        bs.setProperty('-webkit-column-gap', (2*sm)+'px')
        bs.setProperty('-webkit-column-width', col_width+'px')
        bs.setProperty('-webkit-column-rule-color', fgcolor)
        bs.setProperty('overflow', 'visible')
        bs.setProperty('height', 'auto')
        bs.setProperty('width', 'auto')
        bs.setProperty('margin-top', this.margin_top+'px')
        bs.setProperty('margin-bottom', this.margin_bottom+'px')
        bs.setProperty('margin-left', sm+'px')
        bs.setProperty('margin-right', sm+'px')
        for edge in ['left', 'right', 'top', 'bottom']
            bs.setProperty('padding-'+edge, '0px')
            bs.setProperty('border-'+edge+'-width', '0px')
        bs.setProperty('min-width', '0')
        bs.setProperty('max-width', 'none')
        bs.setProperty('min-height', '0')
        bs.setProperty('max-height', 'none')

        # Ensure that the top margin is correct, otherwise for some documents,
        # webkit lays out the body with a lot of space on top
        brect = document.body.getBoundingClientRect()
        if brect.top > this.margin_top
            bs.setProperty('margin-top', (this.margin_top - brect.top)+'px')
        brect = document.body.getBoundingClientRect()
        this.in_paged_mode = true
        this.current_margin_side = sm
        return sm

    scroll_to_pos: (frac) ->
        # Scroll to the position represented by frac (number between 0 and 1)
        xpos = Math.floor(document.body.scrollWidth * frac)
        this.scroll_to_xpos(xpos)

    scroll_to_xpos: (xpos) ->
        # Scroll so that the column containing xpos is the left most column in
        # the viewport
        pos = 0
        until (pos <= xpos < pos + this.page_width)
            pos += this.page_width
        limit = document.body.scrollWidth - this.screen_width
        pos = limit if pos > limit
        window.scrollTo(pos, 0)

    current_pos: (frac) ->
        # The current scroll position as a fraction between 0 and 1
        limit = document.body.scrollWidth - window.innerWidth
        if limit <= 0
            return 0.0
        return window.pageXOffset / limit

    current_column_location: () ->
        # The location of the left edge of the left most column currently
        # visible in the viewport
        x = window.pageXOffset + Math.max(10, this.current_margin_side)
        edge = Math.floor(x/this.page_width)
        while edge < x
            edge += this.page_width
        return edge - this.page_width

    next_screen_location: () ->
        # The position to scroll to for the next screen (which could contain
        # more than one pages). Returns -1 if no further scrolling is possible.
        cc = this.current_column_location()
        ans = cc + this.screen_width
        limit = document.body.scrollWidth - window.innerWidth
        if ans > limit
            ans = if window.pageXOffset < limit then limit else -1
        return ans

    previous_screen_location: () ->
        # The position to scroll to for the previous screen (which could contain
        # more than one pages). Returns -1 if no further scrolling is possible.
        cc = this.current_column_location()
        ans = cc - this.screen_width
        if ans < 0
            # We ignore small scrolls (less than 15px) when going to previous
            # screen
            ans = if window.pageXOffset > 15 then 0 else -1
        return ans

    next_col_location: () ->
        # The position to scroll to for the next column (same as
        # next_screen_location() if columns per screen == 1). Returns -1 if no
        # further scrolling is possible.
        cc = this.current_column_location()
        ans = cc + this.page_width
        limit = document.body.scrollWidth - window.innerWidth
        if ans > limit
            ans = if window.pageXOffset < limit then limit else -1
        return ans

    previous_col_location: () ->
        # The position to scroll to for the previous column (same as
        # previous_screen_location() if columns per screen == 1). Returns -1 if
        # no further scrolling is possible.
        cc = this.current_column_location()
        ans = cc - this.page_width
        if ans < 0
            ans = if window.pageXOffset > 0 then 0 else -1
        return ans

    jump_to_anchor: (name) ->
        elem = document.getElementById(name)
        if !elem
            elems = document.getElementsByName(name)
            if elems
                elem = elems[0]
        if !elem
            return
        elem.scrollIntoView()
        if this.in_paged_mode
            # Ensure we are scrolled to the column containing elem
            this.scroll_to_xpos(absleft(elem) + 5)

if window?
    window.paged_display = new PagedDisplay()

# TODO:
# css pagebreak rules
# CFI and bookmarks
# Go to reference positions
# Indexing
# Resizing of images
# Special handling for identifiable covers (colspan)?
# Full screen mode
