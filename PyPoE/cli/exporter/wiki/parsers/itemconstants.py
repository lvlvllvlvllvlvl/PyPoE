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
    "Metadata/Items/Maps/MapAtlasShapersRealm",
    "Metadata/Items/Maps/MapWorldsShapersRealm",
}

MAPS_OFF_ATLAS = {
    "Metadata/Items/Maps/MapWorldsSynthesisedWorld",
    "Metadata/Items/Maps/MapWorldsChimera",
    "Metadata/Items/Maps/MapWorldsHydra",
    "Metadata/Items/Maps/MapWorldsMinotaur",
    "Metadata/Items/Maps/MapWorldsPhoenix",
    "Metadata/Items/Maps/MapWorldsVaalTemple",
    "Metadata/Items/Maps/MapWorldsHarbingerLow",
    "Metadata/Items/Maps/MapWorldsHarbingerMid",
    "Metadata/Items/Maps/MapWorldsHarbingerHigh",
    "Metadata/Items/Maps/MapWorldsHarbingerUber",
    "Metadata/Items/Maps/MapWorldsTrialmaster",
    "Metadata/Items/Maps/MapWorldsSanctuary",
    "Metadata/Items/Maps/MapWorldsCitadel",
    "Metadata/Items/Maps/MapWorldsFortress",
    "Metadata/Items/Maps/MapWorldsAbomination",
    "Metadata/Items/Maps/MapWorldsZiggurat",
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
    "Metadata/Items/Maps/MapWorldsSynthesisedWorld",
    "Metadata/Items/Maps/MapWorldsChimera",
    "Metadata/Items/Maps/MapWorldsHydra",
    "Metadata/Items/Maps/MapWorldsMinotaur",
    "Metadata/Items/Maps/MapWorldsPhoenix",
    "Metadata/Items/Maps/MapWorldsVaalTemple",
    "Metadata/Items/Maps/MapWorldsHarbingerLow",
    "Metadata/Items/Maps/MapWorldsHarbingerMid",
    "Metadata/Items/Maps/MapWorldsHarbingerHigh",
    "Metadata/Items/Maps/MapWorldsHarbingerUber",
    "Metadata/Items/Maps/MapWorldsTrialmaster",
    "Metadata/Items/Maps/MapWorldsCourtyardOfWasting",
    "Metadata/Items/Maps/MapWorldsChambersOfImpurity",
    "Metadata/Items/Maps/MapWorldsTheatreOfLies",
}

MAPS_TO_SKIP_COMPOSITING = {
    "Metadata/Items/Maps/MapWorldsSynthesisedWorld",
    "Metadata/Items/Maps/MapWorldsHarbingerLow",
    "Metadata/Items/Maps/MapWorldsHarbingerMid",
    "Metadata/Items/Maps/MapWorldsHarbingerHigh",
    "Metadata/Items/Maps/MapWorldsHarbingerUber",
    "Metadata/Items/Maps/MapWorldsTrialmaster",
}

# This is needed because because Mercenaries series has zeroes in the
# tier data for some maps that should not be excluded from the export.
MAP_SERIES_TIERS_OVERRIDE = {
    "Mercenaries": {
        "Metadata/Items/Maps/MapWorldsChimera": 16,
        "Metadata/Items/Maps/MapWorldsHydra": 16,
        "Metadata/Items/Maps/MapWorldsMinotaur": 16,
        "Metadata/Items/Maps/MapWorldsPhoenix": 16,
        "Metadata/Items/Maps/MapWorldsVaalTemple": 16,
        "Metadata/Items/Maps/MapWorldsHarbingerLow": 5,
        "Metadata/Items/Maps/MapWorldsHarbingerMid": 10,
        "Metadata/Items/Maps/MapWorldsHarbingerHigh": 15,
        "Metadata/Items/Maps/MapWorldsHarbingerUber": 16,
        "Metadata/Items/Maps/MapWorldsTrialmaster": 16,
        "Metadata/Items/Maps/MapWorldsSanctuary": 17,
        "Metadata/Items/Maps/MapWorldsCitadel": 17,
        "Metadata/Items/Maps/MapWorldsFortress": 17,
        "Metadata/Items/Maps/MapWorldsAbomination": 17,
        "Metadata/Items/Maps/MapWorldsZiggurat": 17,
    },
}
