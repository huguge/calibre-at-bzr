# calibre: e-book management

## About the upstream

* Author
  * Kovid Goyal
* Web sites
  * URL:http://www.calibre-ebook.com/
  * URL:https://launchpad.net/calibre/
* License
  * GNU GPL v3
* SCM
  * bzr (lp:calibre)


## About this repo

This is a mirror with some tweaks.
(What and how I did is as follows.)


### About branches and tags

* upstream (branch): master branch in lp:calibre
* upstream/\* (tags): tags in lp:calibre.  Prefix 'upstream/' is added by me.
* master (branch): Includes only README.md, about this mirror.


### How to mirror

* Initial clone
  * Setup git-bzr-ng (URL:https://github.com/termie/git-bzr-ng).
  * Do as follows:

            $ git bzr clone lp:calibre calibre
            $ cd calibre
            $ git checkout bzr/master
            $ git branch -m master upstream
            $ # edit .git/config, and rename [bzr "master"] section to [bzr "upstream"].
            $ git gc --aggressive
            $ # You should do this, because repo size at this point would be ~600MiB, but after gc, would be ~80MiB.
            $ # edit .git/packed-refs and add prefix "upstream" to original tags.
  * Done.
* Regular update

        $ git checkout upstream
        $ git bzr sync
        $ # If in need, add prefix "upstream" to original tags.

