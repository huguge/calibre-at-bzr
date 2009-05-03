# -*- coding: utf-8 -*-
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.pdb.ereader.reader import Reader as eReader
from calibre.ebooks.pdb.plucker.reader import Reader as Plucker

FORMATS = {
    'PNPdPPrs' : eReader,
    'PNRdPPrs' : eReader,
    'DataPlkr' : Plucker,
}

IDENTITY_TO_NAME = {
    'PNPdPPrs' : 'eReader',
    'PNRdPPrs' : 'eReader',
    'DataPlkr' : 'Plucker',
}

class PDBError(Exception):
    pass
    

def get_reader(identity):
    '''
    Returns None if no reader is found for the identity.
    '''
    if identity in FORMATS.keys():
        return FORMATS[identity]
    else:
        return None
