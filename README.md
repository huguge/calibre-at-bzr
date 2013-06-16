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

* upstream/master (branch): master branch in lp:calibre
* upstream/\* (tags): tags in lp:calibre.  Prefix 'upstream/' is added by me.
* master (branch): Includes only README.md, about this mirror.


### How to mirror

* Initial clone
  * Do as follows:

            $ mkdir calibre
            $ cd calibre
            $ git remote add upstream bzr::lp:calibre
            $ git config --local --unset remote.upstream.fetch
            $ git config --local --add remote.upstream.fetch '+refs/heads/*:refs/heads/upstream/*'
            $ git config --local --add remote.upstream.fetch '+refs/tags/*:refs/tags/upstream/*'
            $ git config --local --add remote.upstream.tagopt '--no-tags'
            $ git fetch upstream
  * Done.
* Regular update

        $ git fetch upstream

