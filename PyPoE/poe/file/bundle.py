"""
Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/poe/file/dat.py                                            |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
===============================================================================


Agreement
===============================================================================

See PyPoE/LICENSE


Documentation
===============================================================================

Enums
-------------------------------------------------------------------------------

.. autoclass: ENCODE_TYPES

.. authclass: ENCODE_TYPES_HEX

.. autoclass: PATH_TYPES

Classes
-------------------------------------------------------------------------------

.. autoclass: Bundle

.. autoclass: Index

Index Records
-------------------------------------------------------------------------------

.. autoclass: IndexRecord

.. autoclass: BundleRecord

.. autoclass: FileRecord

.. autoclass: DirectoryRecord
"""

# =============================================================================
# Imports
# =============================================================================


# python
import struct
from enum import IntEnum
from io import BytesIO
from typing import Dict, List, Tuple, Union

import ooz

# 3rd party
from fnvhash import fnv1a_64

from PyPoE.poe.file.shared import AbstractFileReadOnly
from PyPoE.shared.mixins import ReprMixin

# self
from PyPoE.shared.murmur2 import murmur2_64a

# =============================================================================
# Setup
# =============================================================================

__all__ = [
    "ENCODE_TYPES",
    "ENCODE_TYPES_HEX",
    "PATH_TYPES",
    "IndexRecord",
    "BundleRecord",
    "FileRecord",
    "DirectoryRecord",
    "Bundle",
    "Index",
]

# =============================================================================
# Classes
# =============================================================================


class HASH_ALGORITHM(IntEnum):
    FNV1A64 = 1
    MURMURHASH64A = 2


class ENCODE_TYPES_HEX(IntEnum):
    NONE = 0xCC07
    LZHLW = 0x8C00
    LZNIB = 0x8C01
    LZB16 = 0x8C02
    LZBLW = 0x8C03
    LZA = 0x8C04
    LZNA = 0x8C05
    KRAKEN = 0x8C06
    LZH = 0x8C07
    # 8, 9?
    MERMAID = 0x8C0A
    SELKIE = MERMAID
    HYDRA = MERMAID

    BITKNIT = 0x8C0B
    LEVIATHAN = 0x8C0C


class ENCODE_TYPES(IntEnum):
    LZH = 0
    LZHLW = 1
    LZNIB = 2
    NONE = 3
    LZB16 = 4
    LZBLW = 5
    LZA = 6
    LZNA = 7
    KRAKEN = 8
    MERMAID = 9
    BITKNIT = 10
    SELKIE = 11
    HYDRA = 12
    LEVIATHAN = 13


class Bundle(AbstractFileReadOnly):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        self.encoder: Union[ENCODE_TYPES, None] = None
        self.unknown: Union[int, None] = None
        self.size_decompressed: Union[int, None] = None
        self.size_compressed: Union[int, None] = None
        self.entry_count: Union[int, None] = None
        self.chunk_size: Union[int, None] = None
        self.unknown3: Union[int, None] = None
        self.unknown4: Union[int, None] = None
        self.unknown5: Union[int, None] = None
        self.unknown6: Union[int, None] = None
        self.chunks: Union[Tuple[int, ...], None] = None
        self.data: Union[Dict[int, bytes], bytes] = {}

    @property
    def is_decompressed(self) -> bool:
        return isinstance(self.data, bytes)

    def _read(self, buffer: BytesIO):
        if self.is_decompressed:
            raise ValueError("Bundle has been decompressed already")

        raw = buffer.read()

        self.uncompressed_size, self.data_size, self.head_size = struct.unpack_from(
            "<III", raw, offset=0
        )
        offset = 12

        data = struct.unpack_from("<IIQQIIIIII", raw, offset=offset)
        offset += 48

        self.encoder = ENCODE_TYPES(data[0])
        self.unknown = data[1]
        self.size_decompressed = data[2]
        self.size_compressed = data[3]
        self.entry_count = data[4]
        self.chunk_size = data[5]
        self.unknown3 = data[6]
        self.unknown4 = data[7]
        self.unknown5 = data[8]
        self.unknown6 = data[9]

        self.chunks = struct.unpack_from("<%sI" % self.entry_count, raw, offset=offset)
        offset += self.entry_count * 4

        for i in range(0, self.entry_count):
            offset2 = offset + self.chunks[i]
            self.data[i] = raw[offset:offset2]

            offset = offset2

    def decompress(self, start: int = 0, end: int = None):
        """
        Decompresses this bundle's contents.

        Parameters
        ----------
        start
            Start chunk
        end
            End chunk
        """
        if not self.data:
            raise ValueError()

        if end is None:
            end = self.entry_count

        last = self.entry_count - 1
        for i in range(start, end):
            if i != last:
                size = self.chunk_size
            else:
                size = self.size_decompressed % self.chunk_size

            out = ooz.decompress(self.data[i], size)
            self.data[i] = bytes(out)

        self.data = b"".join(self.data.values())


class PATH_TYPES(IntEnum):
    DIR = 1
    FILE = 2


class IndexRecord(ReprMixin):
    SIZE = None


class BundleRecord(IndexRecord):
    """
    Attributes
    ----------
    parent : Index
    name : str
    size : int
    contents : Bundle
    BYTES : int
    """

    __slots__ = ["parent", "name", "size", "contents", "BYTES"]

    _REPR_EXTRA_ATTRIBUTES = {x: None for x in __slots__}

    def __init__(self, raw: bytes, parent: "Index", offset: int):
        self.parent: Index = parent

        name_length = struct.unpack_from("<I", raw, offset=offset)[0]

        self.name: str = struct.unpack_from("%ss" % name_length, raw, offset=offset + 4)[0].decode()

        self.size: int = struct.unpack_from("<I", raw, offset=offset + 4 + name_length)[0]

        self.BYTES: int = name_length + 8

        self.contents: Union[Bundle, None] = None

    @property
    def file_name(self) -> str:
        """
        Returns
        -------
        The full filename of this bundle file
        """
        return self.name + ".bundle.bin"

    @property
    def ggpk_path(self) -> str:
        """
        Returns
        -------
        The path relative to the content.ggpk
        """
        return "Bundles2/" + self.file_name

    def read(self, file_path_or_raw: Union[str, bytes]):
        """
        Reads the contents of this bundle if they haven't been read already

        Parameters
        ----------
        file_path_or_raw
            see Bundle.read
        """
        if self.contents is None:
            self.contents = Bundle()
            self.contents.read(file_path_or_raw)
            self.contents.decompress()


class FileRecord(IndexRecord):
    """
    Attributes
    ----------
    parent: Index
    hash: int
    bundle: BundleRecord
    file_offset: int
    file_size: int
    """

    __slots__ = ["parent", "hash", "bundle", "file_offset", "file_size"]

    _REPR_EXTRA_ATTRIBUTES = {x: None for x in __slots__}
    SIZE = 20

    def __init__(self, raw: bytes, parent: "Index", offset: int):
        data = struct.unpack_from("<QIII", raw, offset=offset)

        self.parent: Index = parent
        self.hash: int = data[0]
        self.bundle: BundleRecord = parent.bundles[data[1]]
        self.file_offset: int = data[2]
        self.file_size: int = data[3]

    def get_file(self) -> bytes:
        """
        Returns the file contents associated with this record. For this to work
        the parent's bundle must loaded.

        Returns
        -------
        The contents of the file associated with this record.
        """
        return self.bundle.contents.data[self.file_offset : self.file_offset + self.file_size]


class DirectoryRecord(IndexRecord):
    """
    Attributes
    ----------
    parent: Index
    hash: int
    offset: int
    size: int
    unknown: int
    """

    __slots__ = ["parent", "hash", "offset", "size", "unknown", "_paths"]

    _REPR_EXTRA_ATTRIBUTES = {x: None for x in __slots__}
    SIZE = 20

    def __init__(self, raw: bytes, parent: "Index", offset: int):
        self.parent: Index = parent
        data = struct.unpack_from("<QIII", raw, offset=offset)

        self.hash: int = data[0]
        self.offset: int = data[1]
        self.size: int = data[2]
        self.unknown: int = data[3]
        self._paths = None

    @property
    def path(self) -> str:
        """
        Returns
        -------
            The common path of all file paths contained within this directory
        """
        # Paths can be empty
        if self._paths:
            return self.paths[0].rsplit("/", maxsplit=1)[0]
        else:
            return ""

    @property
    def paths(self) -> List[str]:
        """
        Returns
        -------
            A list of all files with their full paths (relative to the game
            root) contained within this directory
        """
        return [x.decode() for x in self._paths]

    @property
    def files(self) -> List[str]:
        """
        Returns
        -------
            A list of files contained in this directory.
        """
        return [x.rsplit("/", maxsplit=1)[-1] for x in self.paths]


def _hash_path_3_21_2(path, seed):
    if isinstance(path, str):
        path = path.encode("utf-8")
    elif not isinstance(path, bytes):
        raise TypeError("path must be a string")
    if path.endswith(b"/"):
        path = path.strip(b"/")
    path = path.lower()
    return murmur2_64a(path, seed)


class Index(Bundle):
    PATH = "Bundles2/_.index.bin"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bundles: Dict[int, BundleRecord] = {}
        self.files: Dict[int, FileRecord] = {}
        self.directories: Dict[int, DirectoryRecord] = {}

    def get_dir_record(self, path: Union[str, bytes]) -> DirectoryRecord:
        """
        Returns the directory record for the given directory path

        Parameters
        ----------
        path
            Directory path

        Returns
        -------
        DirectoryRecord
            The directory record for the given directory path

        Raises
        ------
        FileNotFoundError
            if the path is not valid
        """
        try:
            return self.directories[self.get_hash(path, type=PATH_TYPES.DIR)]
        except KeyError:
            raise FileNotFoundError()

    def get_file_record(self, path: Union[str, bytes]) -> FileRecord:
        """
        Returns the file record for the given file path

        Parameters
        ----------
        path
            File path

        Returns
        -------
        FileRecord
            The file record for the given file path

        Raises
        ------
        FileNotFoundError
            if the path is not valid
        """
        try:
            return self.files[self.get_hash(path, type=PATH_TYPES.FILE)]
        except KeyError:
            raise FileNotFoundError()

    def get_hash(self, path: Union[str, bytes], type: PATH_TYPES = None) -> int:
        """
        Calculates the 64 bit FNA1a or MurmurHash64A hash value for a given path

        Parameters
        ----------
        path
            path to calculate the hash for
        type
            type of the path (i.e. whether this is a file or directory)

            if not given, it is attempted to infer from the path

        Returns
        -------
        Calculated 64bit hash value
        """
        if self.hash_algorithm == HASH_ALGORITHM.FNV1A64:
            if isinstance(path, str):
                path = path.encode("utf-8")
            elif not isinstance(path, bytes):
                raise TypeError("path must be a string")
            if path.endswith(b"/"):
                if type is None:
                    type = PATH_TYPES.DIR
                path = path.strip(b"/")
            # If type wasn't set before, assume this is a file
            if type == PATH_TYPES.FILE or type is None:
                path = path.lower()
            path += b"++"

            return fnv1a_64(path)
        elif self.hash_algorithm == HASH_ALGORITHM.MURMURHASH64A:
            return _hash_path_3_21_2(path, self.hash_seed)

    def _read(self, buffer: BytesIO):
        if self.bundles:
            raise ValueError("Index bundle has been read already.")
        super()._read(buffer)
        self.decompress()
        raw = self.data

        bundle_count = struct.unpack_from("<I", raw)[0]
        offset = 4

        for i in range(0, bundle_count):
            br = BundleRecord(raw, self, offset)

            self.bundles[i] = br
            offset += br.BYTES

        file_count = struct.unpack_from("<I", raw, offset=offset)[0]
        offset += 4

        for i in range(0, file_count):
            fr = FileRecord(raw, self, offset)
            self.files[fr.hash] = fr
            offset += fr.SIZE

        count = struct.unpack_from("<I", raw, offset=offset)[0]
        offset += 4
        for i in range(0, count):
            dr = DirectoryRecord(raw, self, offset)
            self.directories[dr.hash] = dr
            offset += dr.SIZE

        directory_bundle = Bundle()
        directory_bundle.read(raw[offset:])
        directory_bundle.decompress()

        for directory_record in self.directories.values():
            directory_record._paths = self._make_paths(
                directory_bundle.data[
                    directory_record.offset : directory_record.offset + directory_record.size
                ]
            )

        self.hash_algorithm = None
        if len(dirs := self.directories) > 0:
            dir_iter = iter(dirs.values())
            root_entry = next(dir_iter)
            if root_entry.hash == 0x07E47507B4A92E53:
                self.hash_algorithm = HASH_ALGORITHM.FNV1A64
            else:
                h = root_entry.hash
                # Find seed from root directory hash via inverses
                h ^= h >> 47
                h = (h * 0x5F7A0EA7E59B19BD) % 2**64
                h ^= h >> 47
                self.hash_algorithm = HASH_ALGORITHM.MURMURHASH64A
                self.hash_seed = h

    def _make_paths(self, raw: bytes) -> List[bytes]:
        """

        Parameters
        ----------
        raw
            packed paths

        Returns
        -------
        A list of unpacked paths
        """
        temp = []
        paths = []
        base = False
        offset = 0
        rawlen = len(raw) - 4
        while offset <= rawlen:
            index = struct.unpack_from("<I", raw, offset=offset)[0]
            offset += 4

            if index == 0:
                base = not base
                if base:
                    temp = []
                continue
            else:
                index -= 1

            end_offset = raw.find(b"\x00", offset)
            string = raw[offset:end_offset]
            offset = end_offset + 1

            try:
                string = temp[index] + string
            except IndexError:
                pass  # this is a new string
                pass  # this is a new string

            if base:
                temp.append(string)
            else:
                paths.append(string)

        return paths


if __name__ == "__main__":
    ind = Index()
    ind.read("C:/Temp/Bundles2/_.index.bin")

    print(ind["Metadata/minimap_colours.txt"])

    """b.decompress()
    for var in dir(b):
        if var.startswith('_'):
            continue
        print(var, getattr(b, var))
    """
