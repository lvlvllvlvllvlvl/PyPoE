"""
Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/wiki/parsers/area.py                          |
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

Public API
-------------------------------------------------------------------------------

Interal API
-------------------------------------------------------------------------------
"""

# =============================================================================
# Imports
# =============================================================================

# Python
import re
from functools import partialmethod

# self
from PyPoE.cli.core import Msg, console
from PyPoE.cli.exporter.wiki import parser
from PyPoE.cli.exporter.wiki.handler import ExporterHandler, ExporterResult

# 3rd-party


# =============================================================================
# Globals
# =============================================================================

__all__ = []

# =============================================================================
# Classes
# =============================================================================


class WikiCondition(parser.WikiCondition):
    COPY_KEYS = (
        "main_page",
        "release_version",
        "screenshot_ext",
        "vaal_area_spawn_chance",
    )

    NAME = "Area"
    ADD_INCLUDE = False
    INDENT = 33


class AreaCommandHandler(ExporterHandler):
    def __init__(self, sub_parser, *args, **kwargs):
        super().__init__(self, sub_parser, *args, **kwargs)
        self.parser = sub_parser.add_parser(
            "area",
            help="Area exporter",
        )
        self.parser.set_defaults(func=lambda args: self.parser.print_help())

        area_sub = self.parser.add_subparsers()
        self.add_default_subparser_filters(
            sub_parser=area_sub,
            cls=AreaParser,
        )

        # Filtering
        area_filter_parser = area_sub.add_parser("filter", help="Extract areas using filters")
        self.add_default_parsers(
            parser=area_filter_parser,
            cls=AreaParser,
            func=AreaParser.by_filter,
        )
        area_filter_parser.add_argument(
            "-ft-id",
            "--filter-id",
            "--filter-metadata-id",
            help="Filter area IDs using a regular expression",
            type=str,
            dest="re_id",
        )

    def add_default_parsers(self, *args, **kwargs):
        super().add_default_parsers(*args, **kwargs)
        self.add_format_argument(kwargs["parser"])


class AreaParser(parser.BaseParser):
    _WORLDAREAS_FILE_NAME = "WorldAreas.datc64"
    _MAPPINS_FILE_NAME = "MapPins.datc64"
    _ATLASNODE_FILE_NAME = "AtlasNode.datc64"
    _files = [
        _WORLDAREAS_FILE_NAME,
        _MAPPINS_FILE_NAME,
        _ATLASNODE_FILE_NAME,
    ]

    _area_column_index_filter = partialmethod(
        parser.BaseParser._column_index_filter,
        dat_file_name=_WORLDAREAS_FILE_NAME,
        error_msg="Several areas have not been found:\n%s",
    )

    # Unreleased or disabled areas to avoid exporting to the wiki
    _SKIP_AREAS_BY_ID = [
        "NULL",
        "AncestralTrialTest",
        "AnyAfflictionEndgameArea",
        "AnyCorruptedSideArea",
        "AnyUberTabTrial",
        "BetrayalTest",
        "BlackTest",
        "CharacterSelect",
        "Delve_Empty",
        "Design",
        "DGRMulti",
        "GuildHideout__",
        "HideoutTencentApocalypse",
        "HideoutYaochi",
        "InvasionBoss",
        "Kitavafilming",
        "PersonalHideout",
        "PetFlats",
        "Programming",
        "Programming_Lite",
        "TGRMulti",
        "VFXTest",
    ]

    _COPY_KEYS = (
        (
            "Id",
            {
                "template": "id",
            },
        ),
        (
            "Name",
            {
                "template": "name",
                "condition": lambda v: v,
            },
        ),
        (
            "Act",
            {
                "template": "act",
            },
        ),
        (
            "AreaLevel",
            {
                "template": "area_level",
                "condition": lambda v: v > 0,
            },
        ),
        (
            "MaxLevel",
            {
                "template": "level_restriction_max",
                "condition": lambda v: v < 100,
            },
        ),
        (
            "AreaTypeTags",
            {
                "template": "area_type_tags",
                "condition": lambda v: v,
                "format": lambda v: ", ".join([tag["Id"] for tag in v]),
            },
        ),
        (
            "TagsKeys",
            {
                "template": "tags",
                "condition": lambda v: v,
                "format": lambda v: ", ".join([tag["Id"] for tag in v]),
            },
        ),
        (
            "LoadingScreens",
            {
                "template": "loading_screen",
                "condition": lambda v: v,
                "format": lambda v: (
                    v[0].replace("Art/Textures/Interface/LoadingImages/", "").replace(".dds", "")
                    if v
                    else ""
                ),
            },
        ),
        (
            "Connections_WorldAreasKeys",
            {
                "template": "connection_ids",
                "condition": lambda v: v,
                "format": lambda v: ", ".join(
                    dict.fromkeys(
                        [area["Id"] for area in v if area["Id"] not in AreaParser._SKIP_AREAS_BY_ID]
                    ).keys()
                ),
            },
        ),
        (
            "ParentTown_WorldAreasKey",
            {
                "template": "parent_area_id",
                "condition": lambda v: v,
                "format": lambda v: v["Id"],
            },
        ),
        (
            "ModsKeys",
            {
                "template": "modifier_ids",
                "condition": lambda v: v,
                "format": lambda v: ", ".join([mod["Id"] for mod in v]),
            },
        ),
        (
            "Bosses_MonsterVarietiesKeys",
            {
                "template": "boss_monster_ids",
                "condition": lambda v: v,
                "format": lambda v: ", ".join([mv["Id"] for mv in v]),
            },
        ),
        (
            "Monsters_MonsterVarietiesKeys",
            {
                "template": "monster_ids",
                "condition": lambda v: v,
                "format": lambda v: ", ".join([mv["Id"] for mv in v]),
            },
        ),
        (
            "FirstEntry_NPCTextAudioKey",
            {
                "template": "entry_text",
                "condition": lambda v: v,
                "format": lambda v: v["Text"],
            },
        ),
        (
            "FirstEntry_NPCsKey",
            {
                "template": "entry_npc",
                "condition": lambda v: v,
                "format": lambda v: v["Name"],
            },
        ),
        (
            "VaalArea",
            {
                "template": "vaal_area_ids",
                "condition": lambda v: v,
                "format": lambda v: ", ".join([area["Id"] for area in v]),
            },
        ),
        (
            "IsMapArea",
            {
                "template": "is_map_area",
                "condition": lambda v: v,
            },
        ),
        (
            "IsUniqueMapArea",
            {
                "template": "is_unique_map_area",
                "condition": lambda v: v,
            },
        ),
        (
            "IsTown",
            {
                "template": "is_town_area",
                "condition": lambda v: v,
            },
        ),
        (
            "IsHideout",
            {
                "template": "is_hideout_area",
                "condition": lambda v: v,
            },
        ),
        (
            "IsVaalArea",
            {
                "template": "is_vaal_area",
                "condition": lambda v: v,
            },
        ),
        (
            "IsLabyrinthArea",
            {
                "template": "is_labyrinth_area",
                "condition": lambda v: v,
            },
        ),
        (
            "IsLabyrinthAirlock",
            {
                "template": "is_labyrinth_airlock_area",
                "condition": lambda v: v,
            },
        ),
        (
            "IsLabyrinthBossArea",
            {
                "template": "is_labyrinth_boss_area",
                "condition": lambda v: v,
            },
        ),
        (
            "HasWaypoint",
            {
                "template": "has_waypoint",
                "condition": lambda v: v,
            },
        ),
    )

    def by_rowid(self, parsed_args):
        return self.export(
            parsed_args,
            self.rr[self._WORLDAREAS_FILE_NAME][parsed_args.start : parsed_args.end],
        )

    def by_id(self, parsed_args):
        return self.export(
            parsed_args,
            self._area_column_index_filter(column_id="Id", arg_list=parsed_args.area_id),
        )

    def by_name(self, parsed_args):
        return self.export(
            parsed_args,
            self._area_column_index_filter(column_id="Name", arg_list=parsed_args.area_name),
        )

    def by_filter(self, parsed_args):
        re_id = re.compile(parsed_args.re_id) if parsed_args.re_id else None

        areas = []
        for row in self.rr[self._WORLDAREAS_FILE_NAME]:
            if re_id:
                if not re_id.match(row["Id"]):
                    continue
            areas.append(row)

        return self.export(parsed_args, areas)

    def export(self, parsed_args, areas):
        r = ExporterResult()

        console("Removing disabled areas...")
        areas = [a for a in areas if a["Id"] not in self._SKIP_AREAS_BY_ID]
        areas = [
            a
            for a in areas
            if a["Name"]
            and not a["Name"].startswith("[DNT")
            and not a["Name"].startswith("[UNUSED")
        ]
        console("%s areas left for processing." % len(areas))

        if not areas:
            console(
                "No areas found for the specified parameters. Quitting.",
                msg=Msg.warning,
            )
            return r

        console("Accessing additional data...")
        self.rr[self._MAPPINS_FILE_NAME].build_index("WorldAreasKeys")
        self.rr[self._ATLASNODE_FILE_NAME].build_index("Area2")
        self.rr["MapSeries.dat64"].build_index("Id")
        console("Found %s areas, processing..." % len(areas))

        for area in areas:
            infobox = {}

            # Copy over simple fields from the .dat64
            parser.apply_simple_column_map(infobox, self._COPY_KEYS, area)

            for i, (tag, value) in enumerate(
                zip(area["SpawnWeight_TagsKeys"], area["SpawnWeight_Values"]), start=1
            ):
                infobox["spawn_weight%s_tag" % i] = tag["Id"]
                infobox["spawn_weight%s_value" % i] = value

            map_pin = self.rr[self._MAPPINS_FILE_NAME].index["WorldAreasKeys"].get(area)
            if map_pin:
                infobox["flavour_text"] = map_pin[0]["FlavourText"]

            atlas_node = self.rr[self._ATLASNODE_FILE_NAME].index["Area2"].get(area)
            if atlas_node and "FlavourText" in atlas_node:
                infobox["flavour_text"] = atlas_node["FlavourText"]["Text"]

            cond = WikiCondition(
                data=infobox,
                cmdargs=parsed_args,
            )

            r.add_result(
                text=cond,
                out_file="area_%s.txt" % infobox["id"],
                wiki_page=[
                    {
                        "page": "Area:" + self._format_wiki_title(infobox["id"]),
                        "condition": cond,
                    },
                ],
                wiki_message="Area updater",
            )

        return r


# =============================================================================
# Functions
# =============================================================================
