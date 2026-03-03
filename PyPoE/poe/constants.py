"""
Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/poe/constants.py                                           |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
===============================================================================

Global constants for Path of Exile, such as version or distributor for use in
the functions.

Agreement
===============================================================================

See PyPoE/LICENSE

Documentation
===============================================================================


.. autoclass:: DISTRIBUTOR

.. autoclass:: VERSION
"""

# =============================================================================
# Imports
# =============================================================================

# Python

from enum import EnumMeta, IntEnum

from PyPoE.poe import poe1constants, poe2constants

# 3rd-party

# self

# =============================================================================
# Globals
# =============================================================================

__all__ = ["DISTRIBUTOR", "VERSION", "sequel"]


def sequel(version):
    if version == 1:
        return poe1constants
    else:
        return poe2constants


# =============================================================================
# Classes
# =============================================================================


class IntEnumMetaOverride(EnumMeta):
    def __getitem__(self, item):
        if isinstance(item, int):
            return self(item)
        else:
            return super().__getitem__(item)


class IntEnumOverride(IntEnum, metaclass=IntEnumMetaOverride):
    pass


class VERSION(IntEnumOverride):
    """
    Used to differentiate between the different release versions of the game,
    i.e. between delpoyment (live/stable) version and temporary betas for
    example.

    This constant is primarily virtual and has no direct relevance to the game
    files, but it is used in context of accounting for differences between the
    released versions of available Path of Exile clients.

    Attributes
    ----------
    STABLE
        The stable version of Path of Exile. This will refer to the currently
        playable, public version.
    BETA
        Beta version of Path of Exile.
        As of currently, there is no beta running and this was only used
        for the Awakening Beta.
    ALPHA
        Alpha version of Path of Exile.
    GENERATED
        Schema generated from https://github.com/poe-tool-dev/dat-schema
    ALL
        All registered version types.
    DEFAULT
        Default version (i.e. stable variants). For most use cases this is the
        preferred and default selection.

    """

    STABLE = 1
    BETA = 2
    ALPHA = 4
    GENERATED = 8
    POE2 = 16
    POE2_STABLE = 32

    ALL = STABLE | BETA | ALPHA | GENERATED

    DEFAULT = STABLE


class DISTRIBUTOR(IntEnumOverride):
    """
    Used to differentiate between the different distributors of the clients.

    This constant is primarily virtual and has no direct relevance to the game
    files, but it is used in context of accounting for differences between the
    released versions of available Path of Exile clients.

    Attributes
    ----------
    GGG
        The standalone client
    STEAM
        The international steam client
    GARENA
        Garena client
    INTERNATIONAL
        The international client(s). This generally refers to the clients
        GGG is maintaining itself and share the same realm (i.e. currently
        the standalone and steam client)
    ALL
        All clients
    DEFAULT
        Default selection for clients, i.e. all.
    """

    GGG = 1
    STEAM = 2
    GARENA = 4

    INTERNATIONAL = GGG | STEAM

    ALL = GGG | STEAM | GARENA

    DEFAULT = ALL


# =============================================================================
# Functions
# =============================================================================
