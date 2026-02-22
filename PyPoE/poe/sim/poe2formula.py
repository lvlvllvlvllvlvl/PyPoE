"""
Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/poe/sim/poe2formula.py                                     |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
===============================================================================

Formulas for calculating certain things.

Agreement
===============================================================================

See PyPoE/LICENSE


.. todo::

  Find out the real function for calculating the stat requirement.

Documentation
===============================================================================

.. autoclass:: GemTypes

.. autofunction:: gem_stat_requirement
"""

# =============================================================================
# Imports
# =============================================================================

# Python
import math
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

# self

# =============================================================================
# Globals
# =============================================================================

__all__ = ["GemTypes", "gem_stat_requirement"]

# =============================================================================
# Classes
# =============================================================================


class GemTypes(Enum):
    """
    Attributes
    ----------
    support
        Support Skill Gem
    active
        Active Skill Gem
    meta
        Meta Skill Gem
    """

    support = 1
    active = 2
    meta = 3


# =============================================================================
# Functions
# =============================================================================


def gem_stat_requirement(level=0, multi=100):
    """
    Calculates and returns the stat requirement for the specified level
    requirement.

    .. warning::
        These functions are primarily reverse engineered and may break with
        updates.

    Parameters
    ----------
    level : int
        Level requirement for the current gem level
    multi : int
        Stat multiplier, i.e. from SkillGems.dat


    Returns
    -------
    int
        calculated stat requirement
    """

    _level = 5 + (level - 3) * 1.7
    _multi = math.pow(multi / 100, 0.9)
    result = Decimal(_level * _multi)

    result = int(result.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    result = result + 4

    # Gems seem to have no requirements lower then 8
    return 0 if result < 8 else result
