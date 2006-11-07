##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Defines the structure of packets that are sent to/received from the device. 

Packet structure is defined using classes and inheritance. Each class is a view that imposes
structure on the underlying data buffer. The data buffer is encoded in little-endian format, but you don't
have to worry about that if you are using the classes. The classes have instance variables with getter/setter functions defined
to take care of the encoding/decoding. The classes are intended to mimic C structs. 

There are three kinds of packets. L{Commands<Command>}, L{Responses<Response>}, and L{Answers<Answer>}. 
C{Commands} are sent to the device on the control bus, C{Responses} are received from the device, 
also on the control bus. C{Answers} and their sub-classes represent data packets sent to/received from
the device via bulk transfers. 

Commands are organized as follows: G{classtree Command}

You will typically only use sub-classes of Command. 

Responses are organized as follows: G{classtree Response}

Responses inherit Command as they share header structure.

Answers are organized as follows: G{classtree Answer}
"""

import struct
from errors import PacketError

DWORD     = "<I"    #: Unsigned integer little endian encoded in 4 bytes
DDWORD    = "<Q"    #: Unsigned long long little endian encoded in 8 bytes


class TransferBuffer(list):
  
  """
  Represents raw (unstructured) data packets sent over the usb bus.
  
  C{TransferBuffer} is a wrapper around the tuples used by L{PyUSB<usb>} for communication. 
  It has convenience methods to read and write data from the underlying buffer. See 
  L{TransferBuffer.pack} and L{TransferBuffer.unpack}.
  """
  
  def __init__(self, packet):
    """ 
    Create a L{TransferBuffer} from C{packet} or an empty buffer.
    
    @type packet: integer or listable object
    @param packet: If packet is a list, it is copied into the C{TransferBuffer} and then normalized (see L{TransferBuffer._normalize}).
                   If it is an integer, a zero buffer of that length is created.
    """    
    if "__len__" in dir(packet): 
      list.__init__(self, list(packet))
      self._normalize()
    else: list.__init__(self, [0 for i in range(packet)])
    
  def __add__(self, tb):
    """ Return a TransferBuffer rather than a list as the sum """
    return TransferBuffer(list.__add__(self, tb))
    
  def __getslice__(self, start, end):
    """ Return a TransferBuffer rather than a list as the slice """
    return TransferBuffer(list.__getslice__(self, start, end))
    
  def __str__(self):
    """
    Return a string representation of this buffer.
    
    Packets are represented as hex strings, in 2-byte pairs, S{<=} 16 bytes to a line. An ASCII representation is included. For example::
        0700 0100 0000 0000 0000 0000 0c00 0000         ................
        0200 0000 0400 0000 4461 7461                   ........Data
    """
    ans, ascii = ": ".rjust(10,"0"), ""
    for i in range(0, len(self), 2):
      for b in range(2):
        try: 
          ans   += TransferBuffer.phex(self[i+b])
          ascii += chr(self[i+b]) if self[i+b] > 31 and self[i+b] < 127 else "."
        except IndexError: break      
      ans = ans + " "
      if (i+2)%16 == 0:
        if i+2 < len(self):
          ans += "   " + ascii + "\n" + (TransferBuffer.phex(i+2)+": ").rjust(10, "0")
          ascii = ""
    last_line = ans[ans.rfind("\n")+1:]
    padding = 50 - len(last_line)
    ans += "".ljust(padding) + "   " + ascii
    return ans.strip()
    
  def unpack(self, fmt=DWORD, start=0):
    """ 
    Return decoded data from buffer. 
    
    @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
    @param start: Position in buffer from which to decode
    """
    end = start + struct.calcsize(fmt)    
    return struct.unpack(fmt, "".join([ chr(i) for i in list.__getslice__(self, start, end) ]))
    
  def pack(self, val, fmt=DWORD, start=0):
    """ 
    Encode C{val} and write it to buffer.
    
    @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
    @param start: Position in buffer at which to write encoded data
    """
    self[start:start+struct.calcsize(fmt)] = [ ord(i) for i in struct.pack(fmt, val) ]
  
  def _normalize(self):
    """ Replace negative bytes in C{self} by 256 + byte """
    for i in range(len(self)):
      if self[i] < 0:         
        self[i] = 256 + self[i]    
        
  @classmethod
  def phex(cls, num):
    """ 
    Return the hex representation of num without the 0x prefix. 
  
    If the hex representation is only 1 digit it is padded to the left with a zero. Used in L{TransferBuffer.__str__}.
    """
    index, sign = 2, ""
    if num < 0: 
      index, sign  = 3, "-"
    h=hex(num)[index:]
    if len(h) < 2: 
      h = "0"+h
    return sign + h

      
class field(object):
  """ A U{Descriptor<http://www.cafepy.com/article/python_attributes_and_methods/python_attributes_and_methods.html>}, that implements access
      to protocol packets in a human readable way. 
  """
  def __init__(self, start=16, fmt=DWORD):
    """
    @param start: The byte at which this field is stored in the buffer
    @param fmt:   The packing format for this field. See U{struct<http://docs.python.org/lib/module-struct.html>}.
    """
    self._fmt, self._start = fmt, start    
    
  def __get__(self, obj, typ=None):
    return obj.unpack(start=self._start, fmt=self._fmt)[0]
    
  def __set__(self, obj, val):
    obj.pack(val, start=self._start, fmt=self._fmt)
    
  def __repr__(self):
    if self._fmt == DWORD: typ  = "unsigned int"
    if self._fmt == DDWORD: typ = "unsigned long long"
    return "An " + typ + " stored in " + str(struct.calcsize(self._fmt)) + " bytes starting at byte " + str(self._start)

class stringfield(object):
  """ A field storing a variable length string. """
  def __init__(self, length_field, start=16):
    """
    @param length_field: A U{Descriptor<http://www.cafepy.com/article/python_attributes_and_methods/python_attributes_and_methods.html>} 
                         that returns the length of the string.
    @param start: The byte at which this field is stored in the buffer
    """
    self._length_field = length_field
    self._start = start
    
  def __get__(self, obj, typ=None):
    length = str(self._length_field.__get__(obj))
    return obj.unpack(start=self._start, fmt="<"+length+"s")[0]
    
  def __set__(self, obj, val):
    obj.pack(val, start=self._start, fmt="<"+str(len(val))+"s")
    
  def __repr__(self):
    return "A string starting at byte " + str(self._start)

class Command(TransferBuffer):
  
  """ Defines the structure of command packets sent to the device. """
    
  number = field(start=0, fmt=DWORD)
  """
  Command number. C{unsigned int} stored in 4 bytes at byte 0.
  
  Command numbers are:
       0 GetUsbProtocolVersion
       1 ReqUsbConnect
      
      10 FskFileOpen
      11 FskFileClose
      12 FskGetSize
      13 FskSetSize
      14 FskFileSetPosition
      15 FskGetPosition
      16 FskFileRead
      17 FskFileWrite
      18 FskFileGetFileInfo
      19 FskFileSetFileInfo
      1A FskFileCreate
      1B FskFileDelete
      1C FskFileRename
      
      30 FskFileCreateDirectory
      31 FskFileDeleteDirectory
      32 FskFileRenameDirectory
      33 FskDirectoryIteratorNew
      34 FskDirectoryIteratorDispose
      35 FskDirectoryIteratorGetNext
      
      52 FskVolumeGetInfo
      53 FskVolumeGetInfoFromPath
      
      80 FskFileTerminate
     
     100 ConnectDevice
     101 GetProperty
     102 GetMediaInfo
     103 GetFreeSpace
     104 SetTime
     105 DeviceBeginEnd
     106 UnlockDevice
     107 SetBulkSize 
     
     110 GetHttpRequest
     111 SetHttpRespponse
     112 Needregistration
     114 GetMarlinState
    
     200 ReqDiwStart
     201 SetDiwPersonalkey
     202 GetDiwPersonalkey
     203 SetDiwDhkey
     204 GetDiwDhkey
     205 SetDiwChallengeserver
     206 GetDiwChallengeserver
     207 GetDiwChallengeclient
     208 SetDiwChallengeclient
     209 GetDiwVersion
     20A SetDiwWriteid
     20B GetDiwWriteid
     20C SetDiwSerial
     20D GetDiwModel
     20C SetDiwSerial
     20E GetDiwDeviceid
     20F GetDiwSerial
     210 ReqDiwCheckservicedata
     211 ReqDiwCheckiddata
     212 ReqDiwCheckserialdata
     213 ReqDiwFactoryinitialize
     214 GetDiwMacaddress
     215 ReqDiwTest
     216 ReqDiwDeletekey
    
     300 UpdateChangemode
     301 UpdateDeletePartition
     302 UpdateCreatePartition
     303 UpdateCreatePartitionWithImage
     304 UpdateGetPartitionSize
  """    
  
  type   = field(start=4, fmt=DDWORD) #: Known types are 0x00 and 0x01. Acknowledge commands are always type 0x00
  
  length = field(start=12, fmt=DWORD) #: Length of the data part of this packet
    
  @apply
  def data():
    doc =\
    """ 
    The data part of this command. Returned/set as/by a TransferBuffer. Stored at byte 16.
    
    Setting it by default changes self.length to the length of the new buffer. You may have to reset it to
    the significant part of the buffer. You would normally use the C{command} property of L{ShortCommand} or L{LongCommand} instead.
    """
    def fget(self):
      return self[16:]
      
    def fset(self, buffer):
      self[16:] = buffer
      self.length = len(buffer)
      
    return property(**locals())
  
  def __init__(self, packet):
    """
    @param packet: len(packet) > 15 or packet > 15
    """
    if ("__len__" in dir(packet) and len(packet) < 16) or ("__len__" not in dir(packet) and packet < 16): 
      raise PacketError(str(self.__class__)[7:-2] + " packets must have length atleast 16")    
    TransferBuffer.__init__(self, packet)
  
  
  
class ShortCommand(Command):  
  
  """ A L{Command} whoose data section is 4 bytes long """  
  
  SIZE = 20 #: Packet size in bytes
  command = field(start=16, fmt=DWORD) #: Usually carries additional information
  
  def __init__(self, number=0x00, type=0x00, command=0x00):
    """
    @param number: L{Command.number}
    @param type: L{Command.type}
    @param command: L{ShortCommand.command}
    """
    Command.__init__(self, ShortCommand.SIZE)
    self.number  = number
    self.type    = type
    self.length  = 4
    self.command = command
    
class DirRead(ShortCommand):
  """ The command that asks the device to send the next item in the list """
  NUMBER = 0x35 #: Command number
  def __init__(self, id):
    """ @param id: The identifier returned as a result of a L{DirOpen} command """
    ShortCommand.__init__(self, number=DirRead.NUMBER, type=0x01, command=id)
    
class DirClose(ShortCommand):
  """ Close a previously opened directory """
  NUMBER = 0x34 #: Command number
  def __init__(self, id):
    """ @param id: The identifier returned as a result of a L{DirOpen} command """
    ShortCommand.__init__(self, number=DirClose.NUMBER, type=0x01, command=id)


class LongCommand(Command):
  
  """ A L{Command} whoose data section is 16 bytes long """
  
  SIZE = 32 #: Size in bytes of C{LongCommand} packets
  
  def __init__(self, number=0x00, type=0x00, command=0x00):
    """ 
    @param number: L{Command.number}
    @param type: L{Command.type}
    @param command: L{LongCommand.command}
    """    
    Command.__init__(self, LongCommand.SIZE)
    self.number  = number
    self.type    = type 
    self.length  = 16
    self.command = command
  
  @apply
  def command():
    doc =\
    """ 
    Usually carries extra information needed for the command
    It is a list of C{unsigned integers} of length between 1 and 4. 4 C{unsigned int} stored in 16 bytes at byte 16.
    """
    def fget(self):
      return self.unpack(start=16, fmt="<"+str(self.length/4)+"I")
      
    def fset(self, val):
      if "__len__" not in dir(val): val = (val,)
      start = 16
      for command in val:
        self.pack(command, start=start, fmt=DWORD)
        start += struct.calcsize(DWORD)
      
    return property(**locals())

class PathCommand(Command):
  """ Abstract class that defines structure common to all path related commands. """
  
  path_length = field(start=16, fmt=DWORD)         #: Length of the path to follow
  path        = stringfield(path_length, start=20) #: The path this query is about
  def __init__(self, path, number, path_len_at_byte=16):    
    Command.__init__(self, path_len_at_byte+4+len(path))
    self.path_length = len(path)
    self.path = path
    self.type = 0x01
    self.length = len(self)-16
    self.number = number
    
class FreeSpaceQuery(PathCommand):
  """ Query the free space available """
  NUMBER = 0x53 #; Command number  
  def __init__(self, path):
    PathCommand.__init__(self, path, FreeSpaceQuery.NUMBER)

class DirOpen(PathCommand):  
  """ Open a directory for reading its contents  """  
  NUMBER     = 0x33 #: Command number
  def __init__(self, path):    
    PathCommand.__init__(self, path, DirOpen.NUMBER)


class AcknowledgeBulkRead(LongCommand):
  """ Must be sent to device after a bulk read """
  def __init__(self, bulk_read_id):
    """ bulk_read_id is an integer, the id of the bulk read we are acknowledging. See L{Answer.id} """
    LongCommand.__init__(self, number=0x1000, type=0x00, command=bulk_read_id)    

class DeviceInfoQuery(Command):
  """ The command used to ask for device information """
  NUMBER=0x0101 #: Command number
  def __init__(self):
    Command.__init__(self, 16)
    self.number=DeviceInfoQuery.NUMBER
    self.type=0x01

class FileClose(ShortCommand):
  """ File close command """
  NUMBER = 0x11 #: Command number
  def __init__(self, id):
    ShortCommand.__init__(self, number=FileClose.NUMBER, type=0x01, command=id)

class FileOpen(PathCommand):
  """ File open command """
  NUMBER = 0x10 #: Command number
  READ   = 0x00 #: Open file in read mode
  WRITE  = 0x01 #: Open file in write mode
  path_length = field(start=20, fmt=DWORD)
  path        = stringfield(path_length, start=24)
  
  def __init__(self, path, mode=0x00):
    PathCommand.__init__(self, path, FileOpen.NUMBER, path_len_at_byte=20)
    self.mode = mode
    
  @apply
  def mode():
    doc =\
    """ The file open mode. Is either L{FileOpen.READ} or L{FileOpen.WRITE}. C{unsigned int} stored at byte 16.  """
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
  
  
class FileRead(Command):
  """ Command to read from an open file """
  NUMBER = 0x16 #: Command number to read from a file
  id = field(start=16, fmt=DWORD) #: The file ID returned by a FileOpen command
  offset = field(start=20, fmt=DDWORD) #: offset in the file at which to read
  size = field(start=28, fmt=DWORD)   #: The number of bytes to reead from file.
  def __init__(self, id, offset, size):
    """
    @param id:     File identifier returned by a L{FileOpen} command
    @type id: C{unsigned int}
    @param offset: Position in file at which to read
    @type offset: C{unsigned long long}
    @param size: number of bytes to read
    @type size: C{unsigned int}
  """  
    Command.__init__(self, 32)
    self.number=FileRead.NUMBER
    self.type = 0x01
    self.length = 16
    self.id = id
    self.offset = offset
    self.size = size


class PathQuery(PathCommand):  
  """ Defines structure of command that requests information about a path """  
  NUMBER     = 0x18 #: Command number  
  def __init__(self, path):    
    PathCommand.__init__(self, path, PathQuery.NUMBER)
    
    
class Response(Command):
  """ 
  Defines the structure of response packets received from the device. 
  
  C{Response} inherits from C{Command} as the first 16 bytes have the same structure.
  """
  
  SIZE = 32   #: Size of response packets in the SONY protocol 
  rnumber = field(start=16, fmt=DWORD) #: Response number, the command number of a command packet sent sometime before this packet was received
  
  def __init__(self, packet):
    """ C{len(packet) == Response.SIZE} """
    if len(packet) != Response.SIZE:
        raise PacketError(str(self.__class__)[7:-2] + " packets must have exactly " + str(Response.SIZE) + " bytes not " + str(len(packet)))
    Command.__init__(self, packet)
    if self.number != 0x00001000:
      raise PacketError("Response packets must have their number set to " + hex(0x00001000))
  
  @apply
  def data():
    doc =\
    """ The last 3 DWORDs (12 bytes) of data in this response packet. Returned as a list of unsigned integers. """
    def fget(self):
      return self.unpack(start=20, fmt="<III")
      
    def fset(self, val):
      self.pack(val, start=20, fmt="<III")
      
    return property(**locals())
    
class ListResponse(Response):
  
  """ Defines the structure of response packets received during list (ll) queries. See L{PathQuery}. """
  
  IS_FILE        = 0xffffffd2 #: Queried path is a file 
  IS_INVALID     = 0xfffffff9 #: Queried path is malformed/invalid
  IS_UNMOUNTED   = 0xffffffc8 #: Queried path is not mounted (i.e. a removed storage card/stick)
  IS_EOL         = 0xfffffffa #: There are no more entries in the list
  PATH_NOT_FOUND = 0xffffffd7 #: Queried path is not found 
  
  code = field(start=20, fmt=DWORD) #: Used to indicate conditions like EOL/Error/IsFile etc.
  
  @apply
  def is_file():
    """ True iff queried path is a file """
    def fget(self):      
      return self.code == ListResponse.IS_FILE
    return property(**locals())
    
  @apply
  def is_invalid():
    """ True iff queried path is invalid """
    def fget(self):    
      return self.code == ListResponse.IS_INVALID
    return property(**locals())
    
  @apply
  def path_not_found():
    """ True iff queried path is not found """
    def fget(self):    
      return self.code == ListResponse.PATH_NOT_FOUND
    return property(**locals())
    
  @apply
  def is_unmounted():
    """ True iff queried path is unmounted (i.e. removed storage card) """
    def fget(self):
      return self.code == ListResponse.IS_UNMOUNTED
    return property(**locals())
    
  @apply
  def is_eol():
    """ True iff there are no more items in the list """
    def fget(self):
      return self.code == ListResponse.IS_EOL
    return property(**locals())
    
class Answer(TransferBuffer):
  """ Defines the structure of packets sent to host via a bulk transfer (i.e., bulk reads) """
  
  number = field(start=0, fmt=DWORD) #: Answer identifier, should be sent in an acknowledgement packet
  
  def __init__(self, packet):
    """ @param packet: C{len(packet)} S{>=} C{16} """
    if len(packet) < 16 : raise PacketError(str(self.__class__)[7:-2] + " packets must have a length of atleast 16 bytes")
    TransferBuffer.__init__(self, packet)
    
  
class FileProperties(Answer):
  
  """ Defines the structure of packets that contain size, date and permissions information about files/directories. """
  
  file_size = field(start=16, fmt=DDWORD)
  ctime     = field(start=28, fmt=DDWORD) #: Creation time
  wtime     = field(start=16, fmt=DDWORD) #: Modification time
  
  @apply
  def is_dir():
    doc =\
    """ 
    True if path points to a directory, False if it points to a file. C{unsigned int} stored in 4 bytes at byte 24.
    
    Value of 1 == file and 2 == dir
    """
    
    def fget(self):
      return (self.unpack(start=24, fmt=DWORD)[0] == 2)
      
    def fset(self, val):
      if val: val = 2
      else: val = 1
      self.pack(val, start=24, fmt=DWORD)
      
    return property(**locals())
    
    
  @apply
  def is_readonly():
    doc =\
    """ 
    Whether this file is readonly. C{unsigned int} stored in 4 bytes at byte 36.
    
    A value of 0 corresponds to read/write and 4 corresponds to read-only. The device doesn't send full permissions information.
    """
    
    def fget(self):
      return self.unpack(start=36, fmt=DWORD)[0] != 0
      
    def fset(self, val):
      if val: val = 4
      else: val = 0
      self.pack(val, start=36, fmt=DWORD)
      
    return property(**locals())
    
class IdAnswer(Answer):
  
  """ Defines the structure of packets that contain identifiers for queries. """
  
  @apply
  def id():
    doc =\
    """ The identifier. C{unsigned int} stored in 4 bytes at byte 16. Should be sent in commands asking for the next item in the list. """
    
    def fget(self):
      return self.unpack(start=16, fmt=DWORD)[0]
      
    def fset(self, val):      
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
    
class DeviceInfo(Answer):
  """ Defines the structure of the packet containing information about the device """
  device_name = field(start=16, fmt="<32s")
  device_version = field(start=48, fmt="<32s")
  software_version = field(start=80, fmt="<24s")
  mime_type = field(start=104, fmt="<32s")
  

class FreeSpaceAnswer(Answer):
  total = field(start=24, fmt=DDWORD)
  free_space = field(start=32, fmt=DDWORD)

class ListAnswer(Answer):
  
  """ Defines the structure of packets that contain items in a list. """
  name_length = field(start=20, fmt=DWORD)
  name        = stringfield(name_length, start=24)
  
  @apply
  def is_dir():
    doc =\
    """ True if list item points to a directory, False if it points to a file. C{unsigned int} stored in 4 bytes at byte 16. """
    
    def fget(self):
      return (self.unpack(start=16, fmt=DWORD)[0] == 2)
      
    def fset(self, val):
      if val: val = 2
      else: val = 1
      self.pack(val, start=16, fmt=DWORD)
      
    return property(**locals())
    
  
