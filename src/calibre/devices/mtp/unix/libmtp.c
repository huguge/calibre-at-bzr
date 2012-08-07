#define UNICODE
#include <Python.h>

#include <stdlib.h>
#include <libmtp.h>

#include "devices.h"

// Macros and utilities
#define ENSURE_DEV(rval) \
    if (self->device == NULL) { \
        PyErr_SetString(PyExc_ValueError, "This device has not been initialized."); \
        return rval; \
    }

#define ENSURE_STORAGE(rval) \
    if (self->device->storage == NULL) { \
        PyErr_SetString(PyExc_RuntimeError, "The device has no storage information."); \
        return rval; \
    }

// Storage types
#define ST_Undefined            0x0000
#define ST_FixedROM             0x0001
#define ST_RemovableROM         0x0002
#define ST_FixedRAM             0x0003
#define ST_RemovableRAM         0x0004

// Storage Access capability
#define AC_ReadWrite            0x0000
#define AC_ReadOnly             0x0001
#define AC_ReadOnly_with_Object_Deletion    0x0002

typedef struct {
    PyObject *obj;
    PyThreadState *state;
} ProgressCallback;

static int report_progress(uint64_t const sent, uint64_t const total, void const *const data) {
    PyObject *res;
    ProgressCallback *cb;

    cb = (ProgressCallback *)data;
    if (cb->obj != NULL) {
        PyEval_RestoreThread(cb->state);
        res = PyObject_CallMethod(cb->obj, "report_progress", "KK", sent, total);
        Py_XDECREF(res);
        cb->state = PyEval_SaveThread();
    }
    return 0;
}

static void dump_errorstack(LIBMTP_mtpdevice_t *dev, PyObject *list) {
    LIBMTP_error_t *stack;
    PyObject *err;

    for(stack = LIBMTP_Get_Errorstack(dev); stack != NULL; stack=stack->next) {
        err = Py_BuildValue("Is", stack->errornumber, stack->error_text);
        if (err == NULL) break;
        PyList_Append(list, err);
        Py_DECREF(err);
    }

    LIBMTP_Clear_Errorstack(dev);
}

// }}}

// Device object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    LIBMTP_mtpdevice_t *device;
    PyObject *ids;
    PyObject *friendly_name;
    PyObject *manufacturer_name;
    PyObject *model_name;
    PyObject *serial_number;
    PyObject *device_version;

} libmtp_Device;

// Device.__init__() {{{
static void
libmtp_Device_dealloc(libmtp_Device* self)
{
    if (self->device != NULL) LIBMTP_Release_Device(self->device);
    self->device = NULL;

    Py_XDECREF(self->ids); self->ids = NULL;
    Py_XDECREF(self->friendly_name); self->friendly_name = NULL;
    Py_XDECREF(self->manufacturer_name); self->manufacturer_name = NULL;
    Py_XDECREF(self->model_name); self->model_name = NULL;
    Py_XDECREF(self->serial_number); self->serial_number = NULL;
    Py_XDECREF(self->device_version); self->device_version = NULL;

    self->ob_type->tp_free((PyObject*)self);
}

static int
libmtp_Device_init(libmtp_Device *self, PyObject *args, PyObject *kwds)
{
    int busnum, devnum, vendor_id, product_id;
    PyObject *usb_serialnum;
    char *vendor, *product, *friendly_name, *manufacturer_name, *model_name, *serial_number, *device_version;
    LIBMTP_raw_device_t rawdev;
    LIBMTP_mtpdevice_t *dev;
    size_t i;

    if (!PyArg_ParseTuple(args, "iiiissO", &busnum, &devnum, &vendor_id, &product_id, &vendor, &product, &usb_serialnum)) return -1;

    if (devnum < 0 || devnum > 255 || busnum < 0) { PyErr_SetString(PyExc_TypeError, "Invalid busnum/devnum"); return -1; }

    self->ids = Py_BuildValue("iiiiO", busnum, devnum, vendor_id, product_id, usb_serialnum);
    if (self->ids == NULL) return -1;

    rawdev.bus_location = (uint32_t)busnum;
    rawdev.devnum = (uint8_t)devnum;
    rawdev.device_entry.vendor = vendor;
    rawdev.device_entry.product = product;
    rawdev.device_entry.vendor_id = vendor_id;
    rawdev.device_entry.product_id = product_id;
    rawdev.device_entry.device_flags = 0x00000000U;

    Py_BEGIN_ALLOW_THREADS;
    for (i = 0; ; i++) {
        if (calibre_mtp_device_table[i].vendor == NULL && calibre_mtp_device_table[i].product == NULL && calibre_mtp_device_table[i].vendor_id == 0xffff) break;
        if (calibre_mtp_device_table[i].vendor_id == vendor_id && calibre_mtp_device_table[i].product_id == product_id) {
            rawdev.device_entry.device_flags = calibre_mtp_device_table[i].device_flags;
        }
    }

    // Note that contrary to what the libmtp docs imply, we cannot use
    // LIBMTP_Open_Raw_Device_Uncached as using it causes file listing to fail
    dev = LIBMTP_Open_Raw_Device(&rawdev);
    Py_END_ALLOW_THREADS;

    if (dev == NULL) { 
        PyErr_SetString(PyExc_ValueError, "Unable to open raw device."); 
        return -1;
    }

    self->device = dev;

    Py_BEGIN_ALLOW_THREADS;
    friendly_name = LIBMTP_Get_Friendlyname(self->device);
    manufacturer_name = LIBMTP_Get_Manufacturername(self->device);
    model_name = LIBMTP_Get_Modelname(self->device);
    serial_number = LIBMTP_Get_Serialnumber(self->device);
    device_version = LIBMTP_Get_Deviceversion(self->device);
    Py_END_ALLOW_THREADS;

    if (friendly_name != NULL) {
        self->friendly_name = PyUnicode_FromString(friendly_name);
        free(friendly_name);
    }
    if (self->friendly_name == NULL) { self->friendly_name = Py_None; Py_INCREF(Py_None); }

    if (manufacturer_name != NULL) {
        self->manufacturer_name = PyUnicode_FromString(manufacturer_name);
        free(manufacturer_name);
    }
    if (self->manufacturer_name == NULL) { self->manufacturer_name = Py_None; Py_INCREF(Py_None); }

    if (model_name != NULL) {
        self->model_name = PyUnicode_FromString(model_name);
        free(model_name);
    }
    if (self->model_name == NULL) { self->model_name = Py_None; Py_INCREF(Py_None); }

    if (serial_number != NULL) {
        self->serial_number = PyUnicode_FromString(serial_number);
        free(serial_number);
    }
    if (self->serial_number == NULL) { self->serial_number = Py_None; Py_INCREF(Py_None); }

    if (device_version != NULL) {
        self->device_version = PyUnicode_FromString(device_version);
        free(device_version);
    }
    if (self->device_version == NULL) { self->device_version = Py_None; Py_INCREF(Py_None); }

    return 0;
}
// }}}

// Device.friendly_name {{{
static PyObject *
libmtp_Device_friendly_name(libmtp_Device *self, void *closure) {
    Py_INCREF(self->friendly_name); return self->friendly_name;
} // }}}

// Device.manufacturer_name {{{
static PyObject *
libmtp_Device_manufacturer_name(libmtp_Device *self, void *closure) {
    Py_INCREF(self->manufacturer_name); return self->manufacturer_name;
} // }}}

// Device.model_name {{{
static PyObject *
libmtp_Device_model_name(libmtp_Device *self, void *closure) {
    Py_INCREF(self->model_name); return self->model_name;
} // }}}

// Device.serial_number {{{
static PyObject *
libmtp_Device_serial_number(libmtp_Device *self, void *closure) {
    Py_INCREF(self->serial_number); return self->serial_number;
} // }}}

// Device.device_version {{{
static PyObject *
libmtp_Device_device_version(libmtp_Device *self, void *closure) {
    Py_INCREF(self->device_version); return self->device_version;
} // }}}

// Device.ids {{{
static PyObject *
libmtp_Device_ids(libmtp_Device *self, void *closure) {
    Py_INCREF(self->ids); return self->ids;
} // }}}

// Device.update_storage_info() {{{
static PyObject*
libmtp_Device_update_storage_info(libmtp_Device *self, PyObject *args, PyObject *kwargs) {
    ENSURE_DEV(NULL);
    if (LIBMTP_Get_Storage(self->device, LIBMTP_STORAGE_SORTBY_NOTSORTED) < 0) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to get storage infor for device.");
        return NULL;
    }
    Py_RETURN_NONE;
}
// }}}

// Device.storage_info {{{
static PyObject *
libmtp_Device_storage_info(libmtp_Device *self, void *closure) {
    PyObject *ans, *loc;
    LIBMTP_devicestorage_t *storage;
    ENSURE_DEV(NULL); ENSURE_STORAGE(NULL);

    ans = PyList_New(0);
    if (ans == NULL) { PyErr_NoMemory(); return NULL; }

    for (storage = self->device->storage; storage != NULL; storage = storage->next) {
        // Ignore read only storage
        if (storage->StorageType == ST_FixedROM || storage->StorageType == ST_RemovableROM) continue;
        // Storage IDs with the lower 16 bits 0x0000 are not supposed to be
        // writeable.
        if ((storage->id & 0x0000FFFFU) == 0x00000000U) continue;
        // Also check the access capability to avoid e.g. deletable only storages
        if (storage->AccessCapability == AC_ReadOnly || storage->AccessCapability == AC_ReadOnly_with_Object_Deletion) continue;

        loc = Py_BuildValue("{s:k,s:O,s:K,s:K,s:K,s:s,s:s}", 
                "id", storage->id, 
                "removable", ((storage->StorageType == ST_RemovableRAM) ? Py_True : Py_False),
                "capacity", storage->MaxCapacity,
                "freespace_bytes", storage->FreeSpaceInBytes,
                "freespace_objects", storage->FreeSpaceInObjects,
                "storage_desc", storage->StorageDescription,
                "volume_id", storage->VolumeIdentifier
        );

        if (loc == NULL) return NULL; 
        if (PyList_Append(ans, loc) != 0) return NULL;
        Py_DECREF(loc);

    }

    return ans;
} // }}}

// Device.get_filelist {{{
static PyObject *
libmtp_Device_get_filelist(libmtp_Device *self, PyObject *args, PyObject *kwargs) {
    PyObject *ans, *fo, *callback = NULL, *errs;
    ProgressCallback cb;
    LIBMTP_file_t *f, *tf;

    ENSURE_DEV(NULL); ENSURE_STORAGE(NULL);


    if (!PyArg_ParseTuple(args, "|O", &callback)) return NULL;
    cb.obj = callback;

    ans = PyList_New(0);
    errs = PyList_New(0);
    if (ans == NULL || errs == NULL) { PyErr_NoMemory(); return NULL; }

    cb.state = PyEval_SaveThread();
    tf = LIBMTP_Get_Filelisting_With_Callback(self->device, report_progress, &cb);
    PyEval_RestoreThread(cb.state);

    if (tf == NULL) { 
        dump_errorstack(self->device, errs);
        return Py_BuildValue("NN", ans, errs);
    }

    for (f=tf; f != NULL; f=f->next) {
        fo = Py_BuildValue("{s:k,s:k,s:k,s:s,s:K,s:k}",
                "id", f->item_id,
                "parent_id", f->parent_id,
                "storage_id", f->storage_id,
                "filename", f->filename,
                "size", f->filesize,
                "modtime", f->modificationdate
        );
        if (fo == NULL || PyList_Append(ans, fo) != 0) break;
        Py_DECREF(fo);
    }

    // Release memory
    f = tf;
    while (f != NULL) {
        tf = f; f = f->next; LIBMTP_destroy_file_t(tf);
    }

    if (callback != NULL) {
        // Bug in libmtp where it does not call callback with 100%
        fo = PyObject_CallMethod(callback, "report_progress", "KK", PyList_Size(ans), PyList_Size(ans));
        Py_XDECREF(fo);
    }

    return Py_BuildValue("NN", ans, errs);
} // }}}

// Device.get_folderlist {{{

int folderiter(LIBMTP_folder_t *f, PyObject *parent) {
    PyObject *folder, *children;

    children = PyList_New(0);
    if (children == NULL) { PyErr_NoMemory(); return 1;}

    folder = Py_BuildValue("{s:k,s:k,s:k,s:s,s:N}",
            "id", f->folder_id,
            "parent_d", f->parent_id,
            "storage_id", f->storage_id,
            "name", f->name,
            "children", children);
    if (folder == NULL) return 1;
    PyList_Append(parent, folder);
    Py_DECREF(folder);

    if (f->sibling != NULL) {
        if (folderiter(f->sibling, parent)) return 1;
    }

    if (f->child != NULL) {
        if (folderiter(f->child, children)) return 1;
    }

    return 0;
}

static PyObject *
libmtp_Device_get_folderlist(libmtp_Device *self, PyObject *args, PyObject *kwargs) {
    PyObject *ans, *errs;
    LIBMTP_folder_t *f;

    ENSURE_DEV(NULL); ENSURE_STORAGE(NULL);

    ans = PyList_New(0);
    errs = PyList_New(0);
    if (errs == NULL || ans == NULL) { PyErr_NoMemory(); return NULL; }

    Py_BEGIN_ALLOW_THREADS;
    f = LIBMTP_Get_Folder_List(self->device);
    Py_END_ALLOW_THREADS;

    if (f == NULL) {
        dump_errorstack(self->device, errs);
        return Py_BuildValue("NN", ans, errs);
    }

    if (folderiter(f, ans)) return NULL;
    LIBMTP_destroy_folder_t(f);

    return Py_BuildValue("NN", ans, errs);

} // }}}

static PyMethodDef libmtp_Device_methods[] = {
    {"update_storage_info", (PyCFunction)libmtp_Device_update_storage_info, METH_VARARGS,
     "update_storage_info() -> Reread the storage info from the device (total, space, free space, storage locations, etc.)"
    },

    {"get_filelist", (PyCFunction)libmtp_Device_get_filelist, METH_VARARGS,
     "get_filelist(callback=None) -> Get the list of files on the device. callback must be an object that has a method named 'report_progress(current, total)'. Returns files, errors."
    },

    {"get_folderlist", (PyCFunction)libmtp_Device_get_folderlist, METH_VARARGS,
     "get_folderlist() -> Get the list of folders on the device. Returns files, erros."
    },

    {NULL}  /* Sentinel */
};

static PyGetSetDef libmtp_Device_getsetters[] = {
    {(char *)"friendly_name", 
     (getter)libmtp_Device_friendly_name, NULL,
     (char *)"The friendly name of this device, can be None.",
     NULL},

    {(char *)"manufacturer_name", 
     (getter)libmtp_Device_manufacturer_name, NULL,
     (char *)"The manufacturer name of this device, can be None.",
     NULL},

    {(char *)"model_name", 
     (getter)libmtp_Device_model_name, NULL,
     (char *)"The model name of this device, can be None.",
     NULL},

    {(char *)"serial_number", 
     (getter)libmtp_Device_serial_number, NULL,
     (char *)"The serial number of this device, can be None.",
     NULL},

    {(char *)"device_version", 
     (getter)libmtp_Device_device_version, NULL,
     (char *)"The device version of this device, can be None.",
     NULL},

    {(char *)"ids", 
     (getter)libmtp_Device_ids, NULL,
     (char *)"The ids of the device (busnum, devnum, vendor_id, product_id, usb_serialnum)",
     NULL},

    {(char *)"storage_info",
     (getter)libmtp_Device_storage_info, NULL,
     (char *)"Information about the storage locations on the device. Returns a list of dictionaries where each dictionary corresponds to the LIBMTP_devicestorage_struct.",
     NULL},

    {NULL}  /* Sentinel */
};

static PyTypeObject libmtp_DeviceType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "libmtp.Device",            /*tp_name*/
    sizeof(libmtp_Device),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)libmtp_Device_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "Device",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    libmtp_Device_methods,             /* tp_methods */
    0,             /* tp_members */
    libmtp_Device_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)libmtp_Device_init,      /* tp_init */
    0,                         /* tp_alloc */
    0,                 /* tp_new */
}; // }}}

// }}} End Device object definition

static PyObject *
libmtp_set_debug_level(PyObject *self, PyObject *args) {
    int level;
    if (!PyArg_ParseTuple(args, "i", &level)) return NULL;
    LIBMTP_Set_Debug(level);
    Py_RETURN_NONE;
}


static PyObject *
libmtp_is_mtp_device(PyObject *self, PyObject *args) {
    int busnum, devnum, vendor_id, prod_id, ans = 0;
    size_t i;

    if (!PyArg_ParseTuple(args, "iiii", &busnum, &devnum, &vendor_id, &prod_id)) return NULL;

    for (i = 0; ; i++) {
        if (calibre_mtp_device_table[i].vendor == NULL && calibre_mtp_device_table[i].product == NULL && calibre_mtp_device_table[i].vendor_id == 0xffff) break;
        if (calibre_mtp_device_table[i].vendor_id == vendor_id && calibre_mtp_device_table[i].product_id == prod_id) {
            Py_RETURN_TRUE;
        }
    }

    /*
     * LIBMTP_Check_Specific_Device does not seem to work at least on my linux
     * system. Need to investigate why later. Most devices are in the device
     * table so this is not terribly important.
     */
    /* LIBMTP_Set_Debug(LIBMTP_DEBUG_ALL); */
    /* printf("Calling check: %d %d\n", busnum, devnum); */
    Py_BEGIN_ALLOW_THREADS;
    ans = LIBMTP_Check_Specific_Device(busnum, devnum);
    Py_END_ALLOW_THREADS;

    if (ans) Py_RETURN_TRUE;

    Py_RETURN_FALSE;

}

static PyMethodDef libmtp_methods[] = {
    {"set_debug_level", libmtp_set_debug_level, METH_VARARGS,
        "set_debug_level(level)\n\nSet the debug level bit mask, see LIBMTP_DEBUG_* constants."
    },

    {"is_mtp_device", libmtp_is_mtp_device, METH_VARARGS,
        "is_mtp_device(busnum, devnum, vendor_id, prod_id)\n\nReturn True if the device is recognized as an MTP device by its vendor/product ids. If it is not recognized a probe is done and True returned if the probe succeeds. Note that probing can cause some devices to malfunction, and it is not very reliable, which is why we prefer to use the device database."
    },

    {NULL, NULL, 0, NULL}
};


PyMODINIT_FUNC
initlibmtp(void) {
    PyObject *m;

    libmtp_DeviceType.tp_new = PyType_GenericNew;
    if (PyType_Ready(&libmtp_DeviceType) < 0)
        return;
    
    m = Py_InitModule3("libmtp", libmtp_methods, "Interface to libmtp.");
    if (m == NULL) return;

    LIBMTP_Init();
    LIBMTP_Set_Debug(LIBMTP_DEBUG_NONE);

    Py_INCREF(&libmtp_DeviceType);
    PyModule_AddObject(m, "Device", (PyObject *)&libmtp_DeviceType);

    PyModule_AddStringMacro(m, LIBMTP_VERSION_STRING);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_NONE);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_PTP);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_PLST);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_USB);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_DATA);
    PyModule_AddIntMacro(m, LIBMTP_DEBUG_ALL);
}
