#!/usr/bin/env coffee
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

###
 Copyright 2012, Kovid Goyal <kovid@kovidgoyal.net>
 Released under the GPLv3 License
###

log = window.calibre_utils.log

class PagedDisplay
    # This class is a namespace to expose functions via the
    # window.paged_display object. The most important functions are:
    #
    # set_geometry(): sets the parameters used to layout text in paged mode
    #
    # layout(): causes the currently loaded document to be laid out in columns.

    constructor: () ->
        if not this instanceof arguments.callee
            throw new Error('PagedDisplay constructor called as function')
        this.set_geometry()
        this.page_width = 0
        this.screen_width = 0
        this.in_paged_mode = false
        this.current_margin_side = 0
        this.is_full_screen_layout = false
        this.max_col_width = -1

    set_geometry: (cols_per_screen=1, margin_top=20, margin_side=40, margin_bottom=20) ->
        this.margin_top = margin_top
        this.margin_side = margin_side
        this.margin_bottom = margin_bottom
        this.cols_per_screen = cols_per_screen

    layout: () ->
        # start_time = new Date().getTime()
        body_style = window.getComputedStyle(document.body)
        # When laying body out in columns, webkit bleeds the top margin of the
        # first block element out above the columns, leading to an extra top
        # margin for the page. We compensate for that here. Computing the
        # boundingrect of body is very expensive with column layout, so we do
        # it before the column layout is applied.
        first_layout = false
        if not this.in_paged_mode
            document.body.style.marginTop = '0px'
            extra_margin = document.body.getBoundingClientRect().top
            margin_top = (this.margin_top - extra_margin) + 'px'
            # Check if the current document is a full screen layout like
            # cover, if so we treat it specially.
            single_screen = (document.body.scrollWidth < window.innerWidth + 25 and document.body.scrollHeight < window.innerHeight + 25)
            first_layout = true
        else
            # resize event
            margin_top = body_style.marginTop

        ww = window.innerWidth

        # Calculate the column width so that cols_per_screen columns fit in the
        # window in such a way the right margin of the last column is <=
        # side_margin (it may be less if the window width is not a
        # multiple of n*(col_width+2*side_margin).

        n = this.cols_per_screen
        adjust = ww - Math.floor(ww/n)*n
        # Ensure that the margins are large enough that the adjustment does not
        # cause them to become negative semidefinite
        sm = Math.max(2*adjust, this.margin_side)
        # Minimum column width, for the cases when the window is too
        # narrow
        col_width = Math.max(100, ((ww - adjust)/n) - 2*sm)
        if this.max_col_width > 0 and col_width > this.max_col_width
            # Increase the side margin to ensure that col_width is no larger
            # than max_col_width
            sm += Math.ceil( (col_width - this.max_col_width) / 2*n )
            col_width = Math.max(100, ((ww - adjust)/n) - 2*sm)
        this.page_width = col_width + 2*sm
        this.screen_width = this.page_width * this.cols_per_screen

        fgcolor = body_style.getPropertyValue('color')
        bs = document.body.style

        bs.setProperty('-webkit-column-gap', (2*sm)+'px')
        bs.setProperty('-webkit-column-width', col_width+'px')
        bs.setProperty('-webkit-column-rule-color', fgcolor)
        bs.setProperty('overflow', 'visible')
        bs.setProperty('height', (window.innerHeight - this.margin_top - this.margin_bottom) + 'px')
        bs.setProperty('width', (window.innerWidth - 2*sm)+'px')
        bs.setProperty('margin-top', margin_top)
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

        # Convert page-breaks to column-breaks
        for sheet in document.styleSheets
            for rule in sheet.rules
                if rule.type == 1 # CSSStyleRule
                    for prop in ['page-break-before', 'page-break-after', 'page-break-inside']
                        val = rule.style.getPropertyValue(prop)
                        if val
                            cprop = '-webkit-column-' + prop.substr(5)
                            priority = rule.style.getPropertyPriority(prop)
                            rule.style.setProperty(cprop, val, priority)

        if first_layout
            # Because of a bug in webkit column mode, svg elements defined with
            # width 100% are wider than body and lead to a blank page after the
            # current page (when cols_per_screen == 1). Similarly img elements
            # with height=100% overflow the first column
            has_svg = document.getElementsByTagName('svg').length > 0
            only_img = document.getElementsByTagName('img').length == 1 and document.getElementsByTagName('div').length < 2 and document.getElementsByTagName('p').length < 2
            this.is_full_screen_layout = (only_img or has_svg) and single_screen and document.body.scrollWidth > document.body.clientWidth

        this.in_paged_mode = true
        this.current_margin_side = sm
        # log('Time to layout:', new Date().getTime() - start_time)
        return sm

    fit_images: () ->
        # Ensure no images are wider than the available width in a column. Note
        # that this method use getBoundingClientRect() which means it will
        # force a relayout if the render tree is dirty.
        images = []
        for img in document.getElementsByTagName('img')
            previously_limited = calibre_utils.retrieve(img, 'width-limited', false)
            br = img.getBoundingClientRect()
            left = calibre_utils.viewport_to_document(br.left, 0, doc=img.ownerDocument)[0]
            col = this.column_at(left) * this.page_width
            rleft = left - col - this.current_margin_side
            width  = br.right - br.left
            rright = rleft + width
            col_width = this.page_width - 2*this.current_margin_side
            if previously_limited or rright > col_width
                images.push([img, col_width - rleft])

        for [img, max_width] in images
            img.style.setProperty('max-width', max_width+'px')
            calibre_utils.store(img, 'width-limited', true)

    scroll_to_pos: (frac) ->
        # Scroll to the position represented by frac (number between 0 and 1)
        xpos = Math.floor(document.body.scrollWidth * frac)
        this.scroll_to_xpos(xpos)

    scroll_to_xpos: (xpos, animated=false, notify=false, duration=1000) ->
        # Scroll so that the column containing xpos is the left most column in
        # the viewport
        if typeof(xpos) != 'number'
            log(xpos, 'is not a number, cannot scroll to it!')
            return
        if this.is_full_screen_layout
            window.scrollTo(0, 0)
            return
        pos = Math.floor(xpos/this.page_width) * this.page_width
        limit = document.body.scrollWidth - this.screen_width
        pos = limit if pos > limit
        if animated
            this.animated_scroll(pos, duration=1000, notify=notify)
        else
            window.scrollTo(pos, 0)

    column_at: (xpos) ->
        # Return the number of the column that contains xpos
        return Math.floor(xpos/this.page_width)

    column_boundaries: () ->
        # Return the column numbers at the left edge and after the right edge
        # of the viewport
        l = this.column_at(window.pageXOffset + 10)
        return [l, l + this.cols_per_screen]

    animated_scroll: (pos, duration=1000, notify=true) ->
        # Scroll the window to X-position pos in an animated fashion over
        # duration milliseconds. If notify is true, py_bridge.animated_scroll_done is
        # called.
        delta = pos - window.pageXOffset
        interval = 50
        steps = Math.floor(duration/interval)
        step_size = Math.floor(delta/steps)
        this.current_scroll_animation = {target:pos, step_size:step_size, interval:interval, notify:notify, fn: () =>
            a = this.current_scroll_animation
            npos = window.pageXOffset + a.step_size
            completed = false
            if Math.abs(npos - a.target) < Math.abs(a.step_size)
                completed = true
                npos = a.target
            window.scrollTo(npos, 0)
            if completed
                if notify
                    window.py_bridge.animated_scroll_done()
            else
                setTimeout(a.fn, a.interval)
        }
        this.current_scroll_animation.fn()

    current_pos: (frac) ->
        # The current scroll position as a fraction between 0 and 1
        limit = document.body.scrollWidth - window.innerWidth
        if limit <= 0
            return 0.0
        return window.pageXOffset / limit

    current_column_location: () ->
        # The location of the left edge of the left most column currently
        # visible in the viewport
        if this.is_full_screen_layout
            return 0
        x = window.pageXOffset + Math.max(10, this.current_margin_side)
        return Math.floor(x/this.page_width) * this.page_width

    next_screen_location: () ->
        # The position to scroll to for the next screen (which could contain
        # more than one pages). Returns -1 if no further scrolling is possible.
        if this.is_full_screen_layout
            return -1
        cc = this.current_column_location()
        ans = cc + this.screen_width
        limit = document.body.scrollWidth - window.innerWidth
        if ans > limit
            ans = if window.pageXOffset < limit then limit else -1
        return ans

    previous_screen_location: () ->
        # The position to scroll to for the previous screen (which could contain
        # more than one pages). Returns -1 if no further scrolling is possible.
        if this.is_full_screen_layout
            return -1
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
        if this.is_full_screen_layout
            return -1
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
        if this.is_full_screen_layout
            return -1
        cc = this.current_column_location()
        ans = cc - this.page_width
        if ans < 0
            ans = if window.pageXOffset > 0 then 0 else -1
        return ans

    jump_to_anchor: (name) ->
        # Jump to the element identified by anchor name. Ensures that the left
        # most column in the viewport is the column containing the start of the
        # element and that the scroll position is at the start of the column.
        elem = document.getElementById(name)
        if not elem
            elems = document.getElementsByName(name)
            if elems
                elem = elems[0]
        if not elem
            return
        elem.scrollIntoView()
        if this.in_paged_mode
            # Ensure we are scrolled to the column containing elem
            this.scroll_to_xpos(calibre_utils.absleft(elem) + 5)

    snap_to_selection: () ->
        # Ensure that the viewport is positioned at the start of the column
        # containing the start of the current selection
        if this.in_paged_mode
            sel = window.getSelection()
            r = sel.getRangeAt(0).getBoundingClientRect()
            node = sel.anchorNode
            left = calibre_utils.viewport_to_document(r.left, r.top, doc=node.ownerDocument)[0]

            # Ensure we are scrolled to the column containing the start of the
            # selection
            this.scroll_to_xpos(left+5)

    jump_to_cfi: (cfi) ->
        # Jump to the position indicated by the specified conformal fragment
        # indicator (requires the cfi.coffee library). When in paged mode, the
        # scroll is performed so that the column containing the position
        # pointed to by the cfi is the left most column in the viewport
        window.cfi.scroll_to(cfi, (x, y) =>
            if this.in_paged_mode
                this.scroll_to_xpos(x)
            else
                window.scrollTo(0, y)
        )

    current_cfi: () ->
        # The Conformal Fragment Identifier at the current position, returns
        # null if it could not be calculated. Requires the cfi.coffee library.
        ans = null
        if not window.cfi?
            return ans
        if this.in_paged_mode
            c = this.current_column_location()
            for x in [c, c-this.page_width, c+this.page_width]
                # Try the current column, the previous column and the next
                # column. Each column is tried from top to bottom.
                [left, right] = [x, x + this.page_width]
                if left < 0 or right > document.body.scrollWidth
                    continue
                deltax = Math.floor(this.page_width/25)
                deltay = Math.floor(window.innerHeight/25)
                cury = this.margin_top
                until cury >= (window.innerHeight - this.margin_bottom)
                    curx = left + this.current_margin_side
                    until curx >= (right - this.current_margin_side)
                        cfi = window.cfi.at_point(curx-window.pageXOffset, cury-window.pageYOffset)
                        if cfi
                            log('Viewport cfi:', cfi)
                            return cfi
                        curx += deltax
                    cury += deltay
        else
            try
                ans = window.cfi.at_current()
                if not ans
                    ans = null
            catch err
                log(err)
        if ans
            log('Viewport cfi:', ans)
        return ans

if window?
    window.paged_display = new PagedDisplay()

# TODO:
# Highlight on jump_to_anchor
# Handle document specified margins and allow them to be overridden
