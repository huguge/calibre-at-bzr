.. include:: global.rst

.. _faq:

Frequently Asked Questions
==========================

.. contents:: Contents
  :depth: 1
  :local: 

E-book Format Conversion
-------------------------
.. contents:: Contents
  :depth: 1
  :local:

What formats does |app| support conversion to/from?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| supports the conversion of many input formats to many output formats.
It can convert every input format in the following list, to every output format.

*Input Formats:* CBZ, CBR, CBC, CHM, EPUB, FB2, HTML, LIT, LRF, MOBI, ODT, PDF, PRC**, PDB, PML, RB, RTF, TCR, TXT

*Output Formats:* EPUB, FB2, OEB, LIT, LRF, MOBI, PDB, PML, RB, PDF, TCR, TXT

** PRC is a generic format, |app| supports PRC files with TextRead and MOBIBook headers

.. _best-source-formats:

What are the best source formats to convert?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In order of decreasing preference: LIT, MOBI, EPUB, HTML, PRC, RTF, PDB, TXT, PDF 

Why does the PDF conversion lose some images/tables?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The PDF conversion tries to extract the text and images from the PDF file and convert them to and HTML based ebook. Some PDF files have images in a format that cannot be extracted (vector images). All tables
are also represented as vector diagrams, thus they cannot be extracted.

How do I convert a collection of HTML files in a specific order?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In order to convert a collection of HTML files in a specific oder, you have to create a table of contents file. That is, another HTML file that contains links to all the other files in the desired order. Such a file looks like::
 
   <html>
      <body>
        <h1>Table of Contents</h1>
        <p style="text-indent:0pt">
           <a href="file1.html">First File</a><br/>
           <a href="file2.html">Second File</a><br/>
           .
           .
           .
        </p>
      </body>
   </html>

Then just add this HTML file to the GUI and use the convert button to create your ebook.

.. _char-encoding-faq:

How do I convert my file containing non-English characters, or smart quotes?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There are two aspects to this problem: 
  1. Knowing the encoding of the source file: |app| tries to guess what character encoding your source files use, but often, this is impossible, so you need to tell it what encoding to use. This can be done in the GUI via the :guilabel:`Input character encoding` field in the :guilabel:`Look & Feel` section. The command-line tools all have an :option:`--input-encoding` option.
  2. When adding HTML files to |app|, you may need to tell |app| what encoding the files are in. To do this go to Preferences->Plugins->File Type plugins and customize the HTML2Zip plugin, telling it what encoding your HTML files are in. Now when you add HTML files to |app| they will be correctly processed. HTML files from different sources often have different encodings, so you may have to change this setting repeatedly. A common encoding for many files from the web is ``cp1252`` and I would suggest you try that first. Note that when converting HTML files, leave the input encoding setting mentioned above blank. This is because the HTML2ZIP plugin automatically converts the HTML files to a standard encoding (utf-8). 
  3. Embedding fonts: If you are generating an LRF file to read on your SONY Reader, you are limited by the fact that the Reader only supports a few non-English characters in the fonts it comes pre-loaded with. You can work around this problem by embedding a unicode-aware font that supports the character set your file uses into the LRF file. You should embed atleast a serif and a sans-serif font. Be aware that embedding fonts significantly slows down page-turn speed on the reader. 


How do I use some of the advanced features of the conversion tools?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 You can get help on any individual feature of the converters by mousing over it in the GUI or running ``ebook-convert dummy.html .epub -h`` at a terminal. A good place to start is to look at the following demo files that demonstrate some of the advanced features: 
  * `html-demo.zip <http://calibre-ebook.com/downloads/html-demo.zip>`_ 


Device Integration
-------------------

.. contents:: Contents
  :depth: 1
  :local:

What devices does |app| support?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
At the moment |app| has full support for the SONY PRS 300/500/505/600/700/900, Barnes & Noble Nook, Cybook Gen 3/Opus, Amazon Kindle 1/2/DX, Entourage Edge, Longshine ShineBook, Ectaco Jetbook, BeBook/BeBook Mini, Irex Illiad/DR1000, Foxit eSlick, PocketBook 360, Italica, eClicto, Iriver Story, Airis dBook, Hanvon N515, Binatone Readme, Teclast K3, various Android phones and the iPhone. In addition, using the :guilabel:`Save to disk` function you can use it with any ebook reader that exports itself as a USB disk.

How can I help get my device supported in |app|?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your device appears as a USB disk to the operating system, adding support for it to |app| is very easy.
We just need some information from you:

  * What e-book formats does your device support?
  * Is there a special directory on the device in which all e-book files should be placed?
  * We also need information about your device that |app| will collect automatically. First, if your
    device supports SD cards, insert them. Then connect your device. In calibre go to Preferences->Advanced
    and click the "Debug device detection" button. This will create some debug output. Copy it to a file
    and repeat the process, this time with your device disconnected.
  * Send both the above outputs to us with the other information and we will write a device driver for your 
    device.

Once you send us the output for a particular operating system, support for the device in that operating system
will appear in the next release of |app|.


Can I use both |app| and the SONY software to manage my reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yes, you can use both, provided you do not run them at the same time. That is, you should use the following sequence:
Connect reader->Use one of the programs->Disconnect reader. Reconnect reader->Use the other program->disconnect reader.

The underlying reason is that the Reader uses a single file to keep track
of 'meta' information, such as collections, and this is written to by both
|app| and the Sony software when either updates something on the Reader.
The file will be saved when the Reader is (safely) disconnected, so using one
or the other is safe if there's a disconnection between them, but if
you're not the type to remember this, then the simple answer is to stick
to one or the other for the transfer and just export/import from/to the
other via the computers hard disk.

If you do need to reset your metadata due to problems caused by using both
at the same time, then just delete the media.xml file on the Reader using
your PC's file explorer and it will be recreated after disconnection.

With recent reader iterations, SONY, in all its wisdom has decided to try to force you to
use their software. If you install it, it auto-launches whenever you connect the reader.
If you don't want to uninstall it altogether, there are a couple of tricks you can use. The
simplest is to simply re-name the executable file that launches the library program. More detail
`here <http://www.mobileread.com/forums/showthread.php?t=65809>`_.

Can I use the collections feature of the SONY reader?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| has full support for collections. When you add tags to a book's metadata, those tags are turned into collections when you upload the book to the SONY reader. Also, the series information is automatically
turned into a collection on the reader. Note that the PRS-500 does not support collections for books stored on the SD card. The PRS-505 does. 

How do I use |app| with my iPad/iPhone/iTouch?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can access your calibre library on a iPad/iPhone/iTouch over the air using the calibre content server. 

First perform the following steps in |app|

  * Set the Preferred Output Format in |app| to EPUB (The output format can be set under Preferences->General) 
  * Convert the books you want to read on your iPhone to EPUB format by selecting them and clicking the Convert button.
  * Turn on the Content Server in |app|'s preferences and leave |app| running.

For an iPad:

Install the ReadMe app on your iPad using iTunes. Open Safari and browse to::

    http://192.168.1.2:8080/

Replace ``192.168.1.2`` with the local IP address of the computer running |app|. If you have changed the port the |app| content server is running on, you will have to change ``8080`` as well to the new port. The local IP address is the IP address you computer is assigned on your home network. A quick Google search will tell you how to find out your local IP address.

The books in your |app| library will be presented as a list, 25 entries at a time. Click the right arrow to go to the next 25. You can also type in the search box to find specific books. Just click on the EPUB link of the book you want and it will be downloaded into your ReadMe library.

For an iPhone/iTouch:   

Install the free Stanza reader app on your iPhone/iTouch using iTunes.

Now you should be able to access your books on your iPhone by opening Stanza. Go to "Get Books" and then click the "Shared" tab. Under Shared you will see an entry "Books in calibre". If you don't, make sure your iPhone is connected using the WiFi network in your house, not 3G. If the |app| catalog is still not detected in Stanza, you can add it manually in Stanza. To do this, click the "Shared" tab, then click the "Edit" button and then click "Add book source" to add a new book source. In the Add Book Source screen enter whatever name you like and in the URL field, enter the following::

    http://192.168.1.2:8080/

Replace ``192.168.1.2`` with the local IP address of the computer running |app|. If you have changed the port the |app| content server is running on, you will have to change ``8080`` as well to the new port. The local IP address is the IP address you computer is assigned on your home network. A quick Google search will tell you how to find out your local IP address.   Now click "Save" and you are done.

If you get timeout errors while browsing the calibre catalog in Stanza, try increasing the connection timeout value in the stanza settings. Go to Info->Settings and increase the value of Download Timeout.

How do I use |app| with my Android phone?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First install the WordPlayer e-book reading app from the Android Marketplace onto you phone. Then simply plug your phone into the computer with a USB cable. |app| should automatically detect the phone and then you can transfer books to it by clicking the Send to Device button. |app| does not have support for every single androind device out there, so if you would like to have support for your device added, follow the instructions above for getting your device supported in |app|.

Can I access my |app| books using the web browser in my Kindle or other reading device?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

|app| has a *Content Server* that exports the books in |app| as a web page. You can turn it on under
Preferences->Content Server. Then just point the web browser on your device to the computer running 
the Content Server and you will be able to browse your book collection. For example, if the computer running
the server has IP address 63.45.128.5, in the browser, you would type::

    http://63.45.128.5:8080

Some devices, like the Kindle, do not allow you to access port 8080 (the default port on which the content
server runs. In that case, change the port in the |app| Preferences to 80. (On some operating systems,
you may not be able to run the server on a port number less than 1024 because of security settings. In
this case the simplest solution is to adjust your router to forward requests on port 80 to port 8080).

I get the error message "Failed to start content server: Port 8080 not free on '0.0.0.0'"?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most likely cause of this is your antivirus program. Try temporarily disabling it and see if it does the trick.

Why is my device not detected in linux?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

|app| uses something called SYSFS to detect devices in linux. The linux kernel can export two version of SYSFS, one of which is deprecated. Some linux distributions still ship with kernels that support the deprecated version of SYSFS, even though it was deprecated a long time ago. In this case, device detection in |app| will not work. You can check what version of SYSFS is exported by your kernel with the following command::
    
    grep SYSFS_DEPRECATED /boot/config-`uname -r`

You should see something like ``CONFIG_SYSFS_DEPRECATED_V2 is not set``. If you don't you have to either recompile your kernel with the correct setting, or upgrade your linux distro to a more modern version, where this will not be set.

Library Management
------------------

.. contents:: Contents
  :depth: 1
  :local:

What formats does |app| read metadata from?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| reads metadata from the following formats: CHM, LRF, PDF, LIT, RTF, OPF, MOBI, PRC, EPUB, FB2, IMP, RB, HTML. In addition it can write metadata to: LRF, RTF, OPF, EPUB, PDF, MOBI

Where are the book files stored?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
When you first run |app|, it will ask you for a folder in which to store your books. Whenever you add a book to |app|, it will copy the book into that folder. Books in the folder are nicely arranged into sub-folders by Author and Title. Metadata about the books is stored in the file ``metadata.db`` (which is a sqlite database).

Why doesn't |app| let me store books in my own directory structure?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The whole point of |app|'s library management features is that they provide a search and sort based interface for locating books that is *much* more efficient than any possible directory scheme you could come up with for your collection. Indeed, once you become comfortable using |app|'s interface to find, sort and browse your collection, you wont ever feel the need to hunt through the files on your disk to find a book again. By managing books in its own directory struture of Author -> Title -> Book files, |app| is able to achieve a high level of reliability and standardization. To illustrate why a search/tagging based interface is superior to folders, consider the following. Suppose your book collection is nicely sorted into folders with the following scheme::

    Genre -> Author -> Series -> ReadStatus

Now this makes it very easy to find for example all science fiction books by Isaac Asimov in the Foundation series. But suppose you want to find all unread science fiction books. There's no easy way to do this with this folder scheme, you would instead need a folder scheme that looks like::

    ReadStatus -> Genre -> Author -> Series

In |app|, you would instead use tags to mark genre and read status and then just use a simple search query like ``tag:scifi and not tag:read``. |app| even has a nice graphical interface, so you don't need to learn its search language instead you can just click on tags to include or exclude them from the search. 

Why doesn't |app| have a column for foo?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| is designed to have columns for the most frequently and widely used fields. If it does not have a coulmn for your favorite field, you can always add a tag to the book for that piece of information. |app| also supports a general purpose "comments" fields for longer items.

How do I move my |app| library from one computer to another?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Simply copy the |app| library folder from the old to the new computer. You can find out what the library folder is by clicking Preferences. The very first item is the path to the library folder. Now on the new computer, start |app| for the first time. It will run the Welcome Wizard asking you for the location of the |app| library. Point it to the previously copied folder. 

Note that if you are transferring between different types of computers (for example Windows to OS X) then after doing the above you should also go to Preferences->Advanced and click the Check database integrity button. It will warn you about missing files, if any, which you should then transfer by hand.


Content From The Web
---------------------
.. contents:: Contents
  :depth: 1
  :local:

My downloaded news content causes the reader to reset. 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This is a bug in the SONY firmware. The problem can be mitigated by switching the output format to EPUB
in the configuration dialog. Alternatively, you can use the LRF output format and use the SONY software 
to transfer the files to the reader. The SONY software pre-paginates the LRF file, 
thereby reducing the number of resets.

I obtained a recipe for a news site as a .py file from somewhere, how do I use it?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Start the :guilabel:`Add custom news sources` dialog (from the :guilabel:`Fetch news` menu) and click the :guilabel:`Switch to advanced mode` button. Delete everything in the box with the recipe source code and copy paste the contents of your .py file into the box. Click :guilabel:`Add/update recipe`.


I want |app| to download news from my favorite news website.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you are reasonably proficient with computers, you can teach |app| to download news from any website of your choosing. To learn how to do this see :ref:`news`.

Otherwise, you can register a request for a particular news site by adding a comment `here <http://bugs.calibre-ebook.com/ticket/405>`_.

Can I use web2disk to download an arbitrary website?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``web2disk http://mywebsite.com``

Miscellaneous
--------------

.. contents:: Contents
  :depth: 1
  :local:

Why the name calibre?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Take your pick:
  * Convertor And LIBRary for E-books
  * A high *calibre* product
  * A tribute to the SONY Librie which was the first e-ink based e-book reader
  * My wife chose it ;-)

Why does |app| show only some of my fonts on OS X?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| embeds fonts in ebook files it creates. E-book files support embedding only TrueType (.ttf) fonts. Most fonts on OS X systems are in .dfont format, thus they cannot be embedded. |app| shows only TrueType fonts founf on your system. You can obtain many TrueType fonts on the web. Simply download the .ttf files and add them to the Library/Fonts directory in your home directory. 

|app| is not starting on Windows?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There can be several causes for this:

    * If you get an error about a Python function terminating unexpectedly after upgrading calibre, first uninstall calibre, then delete the folders (if they exists)
      :file:`C:\\Program Files\\Calibre` and :file:`C:\\Program Files\\Calibre2`. Now re-install and you should be fine.
    * If you get an error in the welcome wizard on an initial run of calibre, try choosing a folder like :file:`C:\\library` as the calibre library (calibre sometimes
      has trouble with library locations if the path contains non-English characters, or only numbers, etc.)
    * Try running it as Administrator (Right click on the icon and select "Run as Administrator")
    * **Windows Vista**: If the folder :file:`C:\\Users\\Your User Name\\AppData\\Local\\VirtualStore\\Program Files\\calibre` exists, delete it. Uninstall |app|. Reboot. Re-install.
    * **Any windows version**: Try disabling any antivirus program you have running and see if that fixes it. Also try disabling any firewall software that prevents connections to the local computer.

If it still wont launch, start a command prompt (press the windows key and R; then type :command:`cmd.exe` in the Run dialog that appears). At the command prompt type the following command and press Enter::

    calibre-debug -g

Post any output you see in a help message on the `Forum <http://www.mobileread.com/forums/forumdisplay.php?f=166>`_.

|app| is not starting on OS X?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can obtain debug output about why |app| is not starting by running `Console.app`. Debug output will
be printed to it. If the debug output contains a line that looks like::

    Qt: internal: -108: Error ATSUMeasureTextImage text/qfontengine_mac.mm

then the problem is probably a corrupted font cache. You can clear the cache by following these
`instructions <http://www.macworld.com/article/139383/2009/03/fontcacheclear.html>`_. If that doesn't
solve it, look for a corrupted font file on your system, in ~/Library/Fonts or the like.


My antivirus program claims |app| is a virus/trojan?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Your antivirus program is wrong. |app| is a completely open source product. You can actually browse the source code yourself (or hire someone to do it for you) to verify that it is not a virus. Please report the false identification to whatever company you buy your antivirus software from. If the antivirus program is preventing you from downloading/installing |app|, disable it temporarily, install |app| and then re-enable it.

How do I use purchased EPUB books with |app|?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Most purchased EPUB books have `DRM <http://wiki.mobileread.com/wiki/DRM>`_. This prevents |app| from opening them. You can still use |app| to store and transfer them to your e-book reader. First, you must authorize your reader on a windows machine with Adobe Digital Editions. Once this is done, EPUB books transferred with |app| will work fine on your reader. When you purchase an epub book from a website, you will get an ".acsm" file. This file should be opened with Adobe Digital Editions, which will then download the actual ".epub" e-book. The e-book file will be stored in the folder "My Digital Editions", from where you can add it to |app|.


I want some feature added to |app|. What can I do?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You have two choices: 
 1. Create a patch by hacking on |app| and send it to me for review and inclusion. See `Development <http://calibre-ebook.com/get-involved>`_. 
 2. `Open a ticket <http://bugs.calibre-ebook.com/newticket>`_ (you have to register and login first) and hopefully I will find the time to implement your feature.

Can I include |app| on a CD to be distributed with my product/magazine?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
|app| is licensed under the GNU General Public License v3 (an open source license). This means that you are free to redistribute |app| as long as you make the source code available. So if you want to put |app| on a CD with your product, you must also put the |app| source code on the CD. The source code is available for download `here <http://code.google.com/p/calibre-ebook/downloads/list>`_.


