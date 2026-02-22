"""
MurmurHash2 Python Implementation

Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/shared/murmur2.py                                          |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
===============================================================================

A pure python implementation of the MurmurHash2 algorithm by Austin Appleby.
See also: https://code.google.com/p/smhasher/wiki/MurmurHash

Agreement
===============================================================================

See PyPoE/LICENSE
"""

# =============================================================================
# Imports
# =============================================================================

import struct

# =============================================================================
#  Globals & Constants
# =============================================================================

DEFAULT_SEED = 0
# 'm' and 'r' are mixing constants generated offline.
# They're not really 'magic', they just happen to work well.
M = 0x5BD1E995
R = 24

int32 = 0xFFFFFFFF

# =============================================================================
# Functions
# =============================================================================


def murmur2_32(byte_data, seed=DEFAULT_SEED):
    """
    Creates a murmur2 32 bit integer hash from the given byte_data and seed.

    :param bytes byte_data: the bytes to hash
    :param int seed: seed to initialize this with
    :return int: 32 bit hash
    """

    length = len(byte_data)
    # Initialize the hash to a 'random' value
    h = (seed ^ length) & int32

    # Mix 4 bytes at a time into the hash
    index = 0

    while length >= 4:
        k = struct.unpack("<i", byte_data[index : index + 4])[0]

        k = k * M & int32
        k = k ^ (k >> R & int32)
        k = k * M & int32

        h = h * M & int32
        h = (h ^ k) & int32

        index += 4
        length -= 4

    # Handle the last few bytes of the input array
    if length >= 3:
        h = (h ^ byte_data[index + 2] << 16) & int32
    if length >= 2:
        h = (h ^ byte_data[index + 1] << 8) & int32
    if length >= 1:
        h = (h ^ byte_data[index]) & int32
        h = h * M & int32

    # Do a few final mixes of the hash to ensure the last few bytes are
    # well-incorporated.
    h = h ^ (h >> 13 & int32)
    h = h * M & int32
    h = h ^ (h >> 15 & int32)

    return h


def bytes_to_long(bytes):
    assert len(bytes) == 8
    return sum((b << (k * 8) for k, b in enumerate(bytes)))


# https://gist.github.com/wey-gu/5543c33987c0a5e8f7474b9b80cd36aa
def murmur2_64a(data, seed=0x1337B33F):
    import ctypes

    m = ctypes.c_uint64(0xC6A4A7935BD1E995).value

    r = ctypes.c_uint32(47).value

    MASK = ctypes.c_uint64(2**64 - 1).value

    data_as_bytes = bytearray(data)

    seed = ctypes.c_uint64(seed).value

    h = seed ^ ((m * len(data_as_bytes)) & MASK)

    off = int(len(data_as_bytes) / 8) * 8
    for ll in range(0, off, 8):
        k = bytes_to_long(data_as_bytes[ll : ll + 8])
        k = (k * m) & MASK
        k = k ^ ((k >> r) & MASK)
        k = (k * m) & MASK
        h = h ^ k
        h = (h * m) & MASK

    length = len(data_as_bytes) & 7

    if length >= 7:
        h = h ^ (data_as_bytes[off + 6] << 48)

    if length >= 6:
        h = h ^ (data_as_bytes[off + 5] << 40)

    if length >= 5:
        h = h ^ (data_as_bytes[off + 4] << 32)

    if length >= 4:
        h = h ^ (data_as_bytes[off + 3] << 24)

    if length >= 3:
        h = h ^ (data_as_bytes[off + 2] << 16)

    if length >= 2:
        h = h ^ (data_as_bytes[off + 1] << 8)

    if length >= 1:
        h = h ^ data_as_bytes[off]
        h = (h * m) & MASK

    h = h ^ ((h >> r) & MASK)
    h = (h * m) & MASK
    h = h ^ ((h >> r) & MASK)

    return ctypes.c_uint64(h).value
