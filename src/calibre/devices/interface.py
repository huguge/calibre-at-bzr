__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os
from collections import namedtuple

from calibre.customize import Plugin
from calibre.constants import iswindows

class DevicePlugin(Plugin):
    """
    Defines the interface that should be implemented by backends that
    communicate with an ebook reader.
    """
    type = _('Device Interface')

    #: Ordered list of supported formats
    FORMATS     = ["lrf", "rtf", "pdf", "txt"]

    #: VENDOR_ID can be either an integer, a list of integers or a dictionary
    #: If it is a dictionary, it must be a dictionary of dictionaries,
    #: of the form::
    #:
    #:   {
    #:    integer_vendor_id : { product_id : [list of BCDs], ... },
    #:    ...
    #:   }
    #:
    VENDOR_ID   = 0x0000

    #: An integer or a list of integers
    PRODUCT_ID  = 0x0000
    #: BCD can be either None to not distinguish between devices based on BCD, or
    #: it can be a list of the BCD numbers of all devices supported by this driver.
    BCD         = None

    #: Height for thumbnails on the device
    THUMBNAIL_HEIGHT = 68

    #: Whether the metadata on books can be set via the GUI.
    CAN_SET_METADATA = ['title', 'authors', 'collections']

    # Set this to None if the books on the device are files that the GUI can
    # access in order to add the books from the device to the library
    BACKLOADING_ERROR_MESSAGE = _('Cannot get files from this device')

    #: Path separator for paths to books on device
    path_sep = os.sep

    #: Icon for this device
    icon = I('reader.png')

    # Used by gui2.ui:annotations_fetched() and devices.kindle.driver:get_annotations()
    UserAnnotation = namedtuple('Annotation','type, value')

    #: GUI displays this as a message if not None. Useful if opening can take a
    #: long time
    OPEN_FEEDBACK_MESSAGE = None

    #: Set of extensions that are "virtual books" on the device
    #: and therefore cannot be viewed/saved/added to library
    #: For example: ``frozenset(['kobo'])``
    VIRTUAL_BOOK_EXTENSIONS = frozenset([])

    @classmethod
    def get_gui_name(cls):
        if hasattr(cls, 'gui_name'):
            return cls.gui_name
        if hasattr(cls, '__name__'):
            return cls.__name__
        return cls.name

    # Device detection {{{
    def test_bcd_windows(self, device_id, bcd):
        if bcd is None or len(bcd) == 0:
            return True
        for c in bcd:
            # Bug in winutil.get_usb_devices converts a to :
            rev = ('rev_%4.4x'%c).replace('a', ':')
            if rev in device_id:
                return True
        return False

    def print_usb_device_info(self, info):
        try:
            print '\t', repr(info)
        except:
            import traceback
            traceback.print_exc()

    def is_usb_connected_windows(self, devices_on_system, debug=False,
            only_presence=False):

        def id_iterator():
            if hasattr(self.VENDOR_ID, 'keys'):
                for vid in self.VENDOR_ID:
                    vend = self.VENDOR_ID[vid]
                    for pid in vend:
                        bcd = vend[pid]
                        yield vid, pid, bcd
            else:
                vendors = self.VENDOR_ID if hasattr(self.VENDOR_ID, '__len__') else [self.VENDOR_ID]
                products = self.PRODUCT_ID if hasattr(self.PRODUCT_ID, '__len__') else [self.PRODUCT_ID]
                for vid in vendors:
                    for pid in products:
                        yield vid, pid, self.BCD

        for vendor_id, product_id, bcd in id_iterator():
            vid, pid = 'vid_%4.4x'%vendor_id, 'pid_%4.4x'%product_id
            vidd, pidd = 'vid_%i'%vendor_id, 'pid_%i'%product_id
            for device_id in devices_on_system:
                if (vid in device_id or vidd in device_id) and \
                   (pid in device_id or pidd in device_id) and \
                   self.test_bcd_windows(device_id, bcd):
                       if debug:
                           self.print_usb_device_info(device_id)
                       if only_presence or self.can_handle_windows(device_id, debug=debug):
                           return True
        return False

    def test_bcd(self, bcdDevice, bcd):
        if bcd is None or len(bcd) == 0:
            return True
        for c in bcd:
            if c == bcdDevice:
                return True
        return False

    def is_usb_connected(self, devices_on_system, debug=False,
            only_presence=False):
        '''
        Return True, device_info if a device handled by this plugin is currently connected.

        :param devices_on_system: List of devices currently connected

        '''
        if iswindows:
            return self.is_usb_connected_windows(devices_on_system,
                    debug=debug, only_presence=only_presence), None

        vendors_on_system = set([x[0] for x in devices_on_system])
        vendors = self.VENDOR_ID if hasattr(self.VENDOR_ID, '__len__') else [self.VENDOR_ID]
        if hasattr(self.VENDOR_ID, 'keys'):
            products = []
            for ven in self.VENDOR_ID:
                products.extend(self.VENDOR_ID[ven].keys())
        else:
            products = self.PRODUCT_ID if hasattr(self.PRODUCT_ID, '__len__') else [self.PRODUCT_ID]

        for vid in vendors:
            if vid in vendors_on_system:
                for dev in devices_on_system:
                    cvid, pid, bcd = dev[:3]
                    if cvid == vid:
                        if pid in products:
                            if hasattr(self.VENDOR_ID, 'keys'):
                                cbcd = self.VENDOR_ID[vid][pid]
                            else:
                                cbcd = self.BCD
                            if self.test_bcd(bcd, cbcd):
                                if debug:
                                    self.print_usb_device_info(dev)
                                if self.can_handle(dev, debug=debug):
                                    return True, dev
        return False, None

    # }}}

    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None) :
        """
        :param key: The key to unlock the device
        :param log_packets: If true the packet stream to/from the device is logged
        :param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        :param detected_device: Device information from the device scanner

        """
        raise NotImplementedError()

    def can_handle_windows(self, device_id, debug=False):
        '''
        Optional method to perform further checks on a device to see if this driver
        is capable of handling it. If it is not it should return False. This method
        is only called after the vendor, product ids and the bcd have matched, so
        it can do some relatively time intensive checks. The default implementation
        returns True. This method is called only on windows. See also
        :meth:`can_handle`.

        :param device_info: On windows a device ID string. On Unix a tuple of
                            ``(vendor_id, product_id, bcd)``.

        '''
        return True

    def can_handle(self, device_info, debug=False):
        '''
        Unix version of :meth:`can_handle_windows`

        :param device_info: Is a tupe of (vid, pid, bcd, manufacturer, product,
                            serial number)

        '''

        return True

    def open(self):
        '''
        Perform any device specific initialization. Called after the device is
        detected but before any other functions that communicate with the device.
        For example: For devices that present themselves as USB Mass storage
        devices, this method would be responsible for mounting the device or
        if the device has been automounted, for finding out where it has been
        mounted. The method :meth:`calibre.devices.usbms.device.Device.open` has
        an implementation of
        this function that should serve as a good example for USB Mass storage
        devices.
        '''
        raise NotImplementedError()

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        raise NotImplementedError()

    def post_yank_cleanup(self):
        '''
        Called if the user yanks the device without ejecting it first.
        '''
        raise NotImplementedError()

    def set_progress_reporter(self, report_progress):
        '''
        :param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information

        '''
        raise NotImplementedError()

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.

        :return: (device name, device version, software version on device, mime type)

        """
        raise NotImplementedError()

    def card_prefix(self, end_session=True):
        '''
        Return a 2 element list of the prefix to paths on the cards.
        If no card is present None is set for the card's prefix.
        E.G.
        ('/place', '/place2')
        (None, 'place2')
        ('place', None)
        (None, None)
        '''
        raise NotImplementedError()

    def total_space(self, end_session=True):
        """
        Get total space available on the mountpoints:
            1. Main memory
            2. Memory Card A
            3. Memory Card B

        :return: A 3 element list with total space in bytes of (1, 2, 3). If a
                 particular device doesn't have any of these locations it should return 0.

        """
        raise NotImplementedError()

    def free_space(self, end_session=True):
        """
        Get free space available on the mountpoints:
          1. Main memory
          2. Card A
          3. Card B

        :return: A 3 element list with free space in bytes of (1, 2, 3). If a
                 particular device doesn't have any of these locations it should return -1.

        """
        raise NotImplementedError()

    def books(self, oncard=None, end_session=True):
        """
        Return a list of ebooks on the device.

        :param oncard:  If 'carda' or 'cardb' return a list of ebooks on the
                        specific storage card, otherwise return list of ebooks
                        in main memory of device. If a card is specified and no
                        books are on the card return empty list.

        :return: A BookList.

        """
        raise NotImplementedError()

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        '''
        Upload a list of books to the device. If a file already
        exists on the device, it should be replaced.
        This method should raise a :class:`FreeSpaceError` if there is not enough
        free space on the device. The text of the FreeSpaceError must contain the
        word "card" if ``on_card`` is not None otherwise it must contain the word "memory".

        :param files: A list of paths and/or file-like objects. If they are paths and
                      the paths point to temporary files, they may have an additional
                      attribute, original_file_path pointing to the originals. They may have
                      another optional attribute, deleted_after_upload which if True means
                      that the file pointed to by original_file_path will be deleted after
                      being uploaded to the device.
        :param names: A list of file names that the books should have
                      once uploaded to the device. len(names) == len(files)
        :param metadata: If not None, it is a list of :class:`Metadata` objects.
                         The idea is to use the metadata to determine where on the device to
                         put the book. len(metadata) == len(files). Apart from the regular
                         cover (path to cover), there may also be a thumbnail attribute, which should
                         be used in preference. The thumbnail attribute is of the form
                         (width, height, cover_data as jpeg).

        :return: A list of 3-element tuples. The list is meant to be passed
                 to :meth:`add_books_to_metadata`.
        '''
        raise NotImplementedError()

    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        '''
        Add locations to the booklists. This function must not communicate with
        the device.

        :param locations: Result of a call to L{upload_books}
        :param metadata: List of :class:`Metadata` objects, same as for
                         :meth:`upload_books`.
        :param booklists: A tuple containing the result of calls to
                          (:meth:`books(oncard=None)`,
                          :meth:`books(oncard='carda')`,
                          :meth`books(oncard='cardb')`).

        '''
        raise NotImplementedError

    def delete_books(self, paths, end_session=True):
        '''
        Delete books at paths on device.
        '''
        raise NotImplementedError()

    @classmethod
    def remove_books_from_metadata(cls, paths, booklists):
        '''
        Remove books from the metadata list. This function must not communicate
        with the device.

        :param paths: paths to books on the device.
        :param booklists: A tuple containing the result of calls to
                          (:meth:`books(oncard=None)`,
                          :meth:`books(oncard='carda')`,
                          :meth`books(oncard='cardb')`).

        '''
        raise NotImplementedError()

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.

        :param booklists: A tuple containing the result of calls to
                          (:meth:`books(oncard=None)`,
                          :meth:`books(oncard='carda')`,
                          :meth`books(oncard='cardb')`).

        '''
        raise NotImplementedError()

    def get_file(self, path, outfile, end_session=True):
        '''
        Read the file at ``path`` on the device and write it to outfile.

        :param outfile: file object like ``sys.stdout`` or the result of an
                       :func:`open` call.

        '''
        raise NotImplementedError()

    @classmethod
    def config_widget(cls):
        '''
        Should return a QWidget. The QWidget contains the settings for the device interface
        '''
        raise NotImplementedError()

    @classmethod
    def save_settings(cls, settings_widget):
        '''
        Should save settings to disk. Takes the widget created in
        :meth:`config_widget` and saves all settings to disk.
        '''
        raise NotImplementedError()

    @classmethod
    def settings(cls):
        '''
        Should return an opts object. The opts object should have at least one attribute
        `format_map` which is an ordered list of formats for the device.
        '''
        raise NotImplementedError()

    def set_plugboards(self, plugboards, pb_func):
        '''
        provide the driver the current set of plugboards and a function to
        select a specific plugboard. This method is called immediately before
        add_books and sync_booklists.

        pb_func is a callable with the following signature::
            def pb_func(device_name, format, plugboards)

        You give it the current device name (either the class name or
        DEVICE_PLUGBOARD_NAME), the format you are interested in (a 'real'
        format or 'device_db'), and the plugboards (you were given those by
        set_plugboards, the same place you got this method).

        :return: None or a single plugboard instance.

        '''
        pass

class BookList(list):
    '''
    A list of books. Each Book object must have the fields

      #. title
      #. authors
      #. size (file size of the book)
      #. datetime (a UTC time tuple)
      #. path (path on the device to the book)
      #. thumbnail (can be None) thumbnail is either a str/bytes object with the
         image data or it should have an attribute image_path that stores an
         absolute (platform native) path to the image
      #. tags (a list of strings, can be empty).

    '''

    __getslice__ = None
    __setslice__ = None

    def __init__(self, oncard, prefix, settings):
        pass

    def supports_collections(self):
        ''' Return True if the the device supports collections for this book list. '''
        raise NotImplementedError()

    def add_book(self, book, replace_metadata):
        '''
        Add the book to the booklist. Intent is to maintain any device-internal
        metadata. Return True if booklists must be sync'ed
        '''
        raise NotImplementedError()

    def remove_book(self, book):
        '''
        Remove a book from the booklist. Correct any device metadata at the
        same time
        '''
        raise NotImplementedError()

    def get_collections(self, collection_attributes):
        '''
        Return a dictionary of collections created from collection_attributes.
        Each entry in the dictionary is of the form collection name:[list of
        books]

        The list of books is sorted by book title, except for collections
        created from series, in which case series_index is used.

        :param collection_attributes: A list of attributes of the Book object

        '''
        raise NotImplementedError()

