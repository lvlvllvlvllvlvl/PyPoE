"""
Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/poe/file/it.py                                             |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
===============================================================================

Support for .it file format.

Starting with version 3.20.0 of the game items use .it files instead of .ot

See also:

* :mod:`PyPoE.poe.file.ot`
* :mod:`PyPoE.poe.file.otc`
* :mod:`PyPoE.poe.file.dat`

Agreement
===============================================================================

See PyPoE/LICENSE


Documentation
===============================================================================

.. autoclass:: ITFile
    :exclude-members: clear, copy, default_factory, fromkeys, get, items, keys, pop, popitem, setdefault, update, values

.. autoclass:: ITFileCache

"""  # noqa

# =============================================================================
# Imports
# =============================================================================

# Python

# 3rd-party

from PyPoE.poe.file.shared.keyvalues import (
    AbstractKeyValueFile,
    AbstractKeyValueFileCache,
    AbstractKeyValueSection,
)

# self
from PyPoE.shared.decorators import doc

# =============================================================================
# Globals
# =============================================================================

__all__ = ["ITFile", "ITFileCache"]

# =============================================================================
# Classes
# =============================================================================


class BaseKeyValueSection(AbstractKeyValueSection):
    NAME = "Base"
    ORDERED_HASH_KEYS = {"tag"}


class ModsKeyValueSection(AbstractKeyValueSection):
    NAME = "Mods"
    ORDERED_HASH_KEYS = {"enable_rarity"}


class SocketsKeyValueSection(AbstractKeyValueSection):
    NAME = "Sockets"


class StatsKeyValueSection(AbstractKeyValueSection):
    NAME = "Stats"


class ImprintKeyValueSection(AbstractKeyValueSection):
    NAME = "Imprint"


@doc(append=AbstractKeyValueFile)
class ITFile(AbstractKeyValueFile):
    """
    Representation of a .it file.
    """

    SECTIONS = dict(
        (s.NAME, s)
        for s in [
            BaseKeyValueSection,
            ModsKeyValueSection,
            SocketsKeyValueSection,
            StatsKeyValueSection,
            ImprintKeyValueSection,
        ]
    )

    EXTENSION = ".it"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


@doc(append=AbstractKeyValueFileCache)
class ITFileCache(AbstractKeyValueFileCache[ITFile]):
    """
    Cache for ITFile instances.
    """

    FILE_TYPE = ITFile
