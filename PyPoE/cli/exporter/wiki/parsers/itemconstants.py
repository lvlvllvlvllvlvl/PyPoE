"""
Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/wiki/parsers/itemconstants.py                 |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | angelic_knight                                                   |
+----------+------------------------------------------------------------------+

Description
===============================================================================

Global constants the item exporter such as lists of items to exclude from exporting.

Agreement
===============================================================================

See PyPoE/LICENSE

Documentation
===============================================================================
"""

# =============================================================================
# Imports
# =============================================================================

# Python

# 3rd-party

# self

# =============================================================================
# Globals
# =============================================================================

MAPS_SKIP_EXPORT = {
    "Metadata/Items/Maps/MapWorldsShapersRealm",
}

MAPS_OFF_ATLAS = {
    "Metadata/Items/Maps/MapWorldsHarbingerUber",
    "Metadata/Items/Maps/MapWorldsHarbingerHigh",
    "Metadata/Items/Maps/MapWorldsHarbingerMid",
    "Metadata/Items/Maps/MapWorldsHarbingerLow",
    "Metadata/Items/Maps/MapWorldsPhoenix",
    "Metadata/Items/Maps/MapWorldsChimera",
    "Metadata/Items/Maps/MapWorldsHydra",
    "Metadata/Items/Maps/MapWorldsMinotaur",
    "Metadata/Items/Maps/MapWorldsVaalTemple",
    "Metadata/Items/Maps/MapWorldsSynthesisedWorld",
    "Metadata/Items/Maps/MapWorldsTrialmaster",
    "Metadata/Items/Maps/MapWorldsCourtyardOfWasting",
    "Metadata/Items/Maps/MapWorldsChambersOfImpurity",
    "Metadata/Items/Maps/MapWorldsTheatreOfLies",
}

MAPS_UBER_MEMORY = {
    "Metadata/Items/Maps/MapWorldsCourtyardOfWasting",
    "Metadata/Items/Maps/MapWorldsChambersOfImpurity",
    "Metadata/Items/Maps/MapWorldsTheatreOfLies",
}

MAPS_TO_SKIP_COLORING = {
    "Metadata/Items/Maps/MapWorldsHarbingerUber",
    "Metadata/Items/Maps/MapWorldsHarbingerHigh",
    "Metadata/Items/Maps/MapWorldsHarbingerMid",
    "Metadata/Items/Maps/MapWorldsHarbingerLow",
    "Metadata/Items/Maps/MapWorldsPhoenix",
    "Metadata/Items/Maps/MapWorldsChimera",
    "Metadata/Items/Maps/MapWorldsHydra",
    "Metadata/Items/Maps/MapWorldsMinotaur",
    "Metadata/Items/Maps/MapWorldsVaalTemple",
    "Metadata/Items/Maps/MapWorldsSynthesisedWorld",
    "Metadata/Items/Maps/MapWorldsTrialmaster",
    "Metadata/Items/Maps/MapWorldsCourtyardOfWasting",
    "Metadata/Items/Maps/MapWorldsChambersOfImpurity",
    "Metadata/Items/Maps/MapWorldsTheatreOfLies",
}

MAPS_TO_SKIP_COMPOSITING = {
    "Metadata/Items/Maps/MapWorldsHarbingerUber",
    "Metadata/Items/Maps/MapWorldsHarbingerHigh",
    "Metadata/Items/Maps/MapWorldsHarbingerMid",
    "Metadata/Items/Maps/MapWorldsHarbingerLow",
    "Metadata/Items/Maps/MapWorldsSynthesisedWorld",
    "Metadata/Items/Maps/MapWorldsTrialmaster",
}
