"""
Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/poe2wiki/parsers/area.py                      |
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
from collections import OrderedDict
from functools import partialmethod

# self
from PyPoE.cli.core import Msg, console
from PyPoE.cli.exporter.poe2wiki import parser
from PyPoE.cli.exporter.poe2wiki.handler import ExporterHandler, ExporterResult

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
        "is_underground",
        "entry_text",  # temp
        "screenshot",
        "screenshot_ext",
        "main_page",
        "release_version",
        "removal_version",
    )

    NAME = "Area"
    ADD_INCLUDE = False
    INDENT = 33


class AreaCommandHandler(ExporterHandler):
    def __init__(self, sub_parser):
        self.parser = sub_parser.add_parser(
            "area",
            help="Area Exporter",
        )
        self.parser.set_defaults(func=lambda args: self.parser.print_help())

        sub = self.parser.add_subparsers()

        # By id
        a_id = sub.add_parser("id", help="Extract areas by their id.")
        self.add_default_parsers(
            parser=a_id,
            cls=AreaParser,
            func=AreaParser.by_id,
        )
        a_id.add_argument(
            "area_id",
            help="Id of the area, can be specified multiple times.",
            nargs="+",
        )

        # by name
        a_name = sub.add_parser("name", help="Extract areas by their name.")
        self.add_default_parsers(
            parser=a_name,
            cls=AreaParser,
            func=AreaParser.by_name,
        )
        a_name.add_argument(
            "area_name",
            help="Visible name of the area (localized), can be specified multiple times.",
            nargs="+",
        )

        # by row ID
        a_rid = sub.add_parser("rowid", help="Extract areas by rowid.")
        self.add_default_parsers(
            parser=a_rid,
            cls=AreaParser,
            func=AreaParser.by_rowid,
        )
        a_rid.add_argument(
            "start",
            help="Starting index",
            nargs="?",
            type=int,
            default=0,
        )
        a_rid.add_argument(
            "end",
            nargs="?",
            help="Ending index",
            type=int,
        )

        # filtering
        a_filter = sub.add_parser("filter", help="Extract areas using filters.")
        self.add_default_parsers(
            parser=a_filter,
            cls=AreaParser,
            func=AreaParser.by_filter,
        )

        a_filter.add_argument(
            "-ft-id",
            "--filter-id",
            "--filter-metadata-id",
            help="Regular expression on the id",
            type=str,
            dest="re_id",
        )

    def add_default_parsers(self, *args, **kwargs):
        super().add_default_parsers(*args, **kwargs)
        parser = kwargs["parser"]
        self.add_format_argument(parser)

        parser.add_argument(
            "--skip-main-page",
            help="Skip adding main_page argument to the template",
            action="store_true",
            default=False,
            dest="skip_main_page",
        )


class AreaParser(parser.BaseParser):
    _files = [
        "WorldAreas.datc64",
        "MapPins.datc64",
        "EndgameMaps.datc64",
    ]

    _area_column_index_filter = partialmethod(
        parser.BaseParser._column_index_filter,
        dat_file_name="WorldAreas.dat64",
        error_msg="Several areas have not been found:\n%s",
    )

    # Unreleased or disabled areas to avoid exporting to the wiki
    _SKIP_AREAS_BY_ID = [
        "NULL",  # 0.1.0
        "BlackTest",  # 0.3.1
        "Design",  # 0.3.1
        "Design_Lite",  # 0.3.1
        "Programming",  # 0.3.1
        "Programming_Lite",  # 0.3.1
        "G1_10",
        "G2_3s",
        "G2_8a",
        "G2_11",
        "G3_15",
        "G4_6",  # 0.3.0
        "G4_9_",  # 0.3.0
        "G4_12",  # 0.3.0
        "G4_14",  # 0.3.0
    ]

    _COPY_KEYS = OrderedDict(
        (
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
                },
            ),
            (
                "MaxLevel",
                {
                    "template": "level_restriction_max",
                    "default": 100,
                },
            ),
            # (
            #    "AreaType_TagsKeys",
            #    {
            #        "template": "area_type_tags",
            #        "format": lambda value: ", ".join([tag["Id"] for tag in value]),
            #        "default": [],
            #    },
            # ),
            (
                "Tags",
                {
                    "template": "tags",
                    "format": lambda value: ", ".join([tag["Id"] for tag in value]),
                    "default": [],
                },
            ),
            (
                "LoadingScreens",
                {
                    "template": "loading_screen",
                    "format": lambda value: (
                        value[0]
                        .replace("Art/Textures/Interface/LoadingImages/", "")
                        .replace(".dds", "")
                        if value
                        else ""
                    ),
                    "default": [],
                },
            ),
            (
                "Connections",
                {
                    "template": "connection_ids",
                    "format": lambda value: ", ".join(
                        OrderedDict.fromkeys(
                            [
                                area["Id"]
                                for area in value
                                if area["Id"] not in AreaParser._SKIP_AREAS_BY_ID
                            ]
                        ).keys()
                    ),
                    "default": [],
                },
            ),
            (
                "ParentTown",
                {
                    "template": "parent_area_id",
                    "format": lambda value: value["Id"],
                },
            ),
            # ( TODO:REMOVE: Unnote when mods will be exported
            #    "AreaMods",
            #    {
            #        "template": "modifier_ids",
            #        "format": lambda value: ", ".join([mod["Id"] for mod in value]),
            #        "default": [],
            #    },
            # ),
            (
                "Bosses",
                {
                    "template": "boss_monster_ids",
                    "format": lambda value: ", ".join([mv["Id"] for mv in value]),
                    "default": [],
                },
            ),
            # (
            #    "Monsters_MonsterVarietiesKeys",
            #    {
            #        "template": "monster_ids",
            #        "format": lambda value: ", ".join([mv["Id"] for mv in value]),
            #        "default": [],
            #    },
            # ),
            # (
            #    "FirstEntry_NPCTextAudioKey",
            #    {
            #        "template": "entry_text",
            #        "format": lambda value: value["Text"],
            #    },
            # ),
            # (
            #    "FirstEntry_NPCsKey",
            #    {
            #        "template": "entry_npc",
            #        "condition": lambda area: area["FirstEntry_NPCTextAudioKey"] is not None,
            #        "format": lambda value: value["Name"],
            #    },
            # ),
            # (
            #    "VaalArea_WorldAreasKeys",
            #    {
            #        "template": "vaal_area_ids",
            #        "condition": lambda area: area["VaalArea_WorldAreasKeys"],
            #        "format": lambda value: ", ".join([area["Id"] for area in value]),
            #    },
            # ),
            # ('Strongbox_SpawnChance', {
            #     'template': 'strongbox_spawn_chance',
            #     'condition': lambda area: area['Strongbox_SpawnChance'] > 0,
            # }),
            # ('Strongbox_MaxCount', {
            #     'template': 'strongbox_max',
            #     'condition': lambda area: area['Strongbox_SpawnChance'] > 0,
            #     'default': 0,
            # }),
            # ('Strongbox_RarityWeight', {
            #     'template': 'strongbox_rarity_weight',
            #     'condition': lambda area: area['Strongbox_SpawnChance'] > 0,
            #     'default': '',
            #     'format': lambda value: ', '.join([str(v) for v in value]),
            # }),
            # bools
            (
                "IsMapArea",
                {
                    "template": "is_map_area",
                    "default": False,
                },
            ),
            (
                "IsUniqueMapArea",
                {
                    "template": "is_unique_map_area",
                    "default": False,
                },
            ),
            (
                "IsTown",
                {
                    "template": "is_town_area",
                    "default": False,
                },
            ),
            (
                "IsHideout",
                {
                    "template": "is_hideout_area",
                    "default": False,
                },
            ),
            # (
            #    "IsVaalArea",
            #    {
            #        "template": "is_vaal_area",
            #        "default": False,
            #    },
            # ),
            # (
            #    "IsLabyrinthArea",
            #    {
            #        "template": "is_labyrinth_area",
            #        "default": False,
            #    },
            # ),
            # (
            #    "IsLabyrinthAirlock",
            #    {
            #        "template": "is_labyrinth_airlock_area",
            #        "default": False,
            #    },
            # ),
            # (
            #    "IsLabyrinthBossArea",
            #    {
            #        "template": "is_labyrinth_boss_area",
            #        "default": False,
            #    },
            # ),
            (
                "HasWaypoint",
                {
                    "template": "has_waypoint",
                    "default": False,
                },
            ),
        )
    )

    def by_rowid(self, parsed_args):
        return self.export(
            parsed_args,
            self.rr["WorldAreas.dat64"][parsed_args.start : parsed_args.end],
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

        out = []
        for row in self.rr["WorldAreas.dat64"]:
            if re_id:
                if not re_id.match(row["Id"]):
                    continue
            out.append(row)

        return self.export(parsed_args, out)

    def export(self, parsed_args, areas):
        console("Found %s areas, parsing..." % len(areas))

        r = ExporterResult()

        if not areas:
            console(
                "No areas found for the specified parameters. Quitting.",
                msg=Msg.warning,
            )
            return r

        console("Accessing additional data...")

        self.rr["MapPins.dat64"].build_index("WorldAreasKeys")
        self.rr["EndgameMaps.dat64"].build_index("WorldArea")

        console("Found %s areas. Removing disabled areas..." % len(areas))
        areas = [area for area in areas if area["Id"] not in self._SKIP_AREAS_BY_ID]
        console("%s areas left for processing." % len(areas))

        # console("Found %s areas. Processing..." % len(areas))

        for area in areas:
            # if "[DNT]" in area["Name"] or "[DNT-UNUSED]" in area["Name"]:
            #    continue
            data = OrderedDict()

            for row_key, copy_data in self._COPY_KEYS.items():
                value = area[row_key]

                if copy_data.get("condition") and not copy_data["condition"](value):
                    continue

                # Skip default values to reduce size of template
                if value == copy_data.get("default"):
                    continue
                """default = copy_data.get('default')
                if default is not None and value == default:
                        continue"""

                fmt = copy_data.get("format")
                if fmt:
                    value = fmt(value)
                data[copy_data["template"]] = value

            # for i, (tag, value) in enumerate(
            #    zip(area["SpawnWeight_TagsKeys"], area["SpawnWeight_Values"]), start=1
            # ):
            #    data["spawn_weight%s_tag" % i] = tag["Id"]
            #    data["spawn_weight%s_value" % i] = value

            map_pin = self.rr["MapPins.dat64"].index["WorldAreasKeys"].get(area)
            if map_pin:
                data["flavour_text"] = map_pin[0]["FlavourText"]

            endgame_map = self.rr["EndgameMaps.dat64"].index["WorldArea"].get(area)
            if endgame_map:
                data["flavour_text"] = endgame_map["FlavourText"]

                biomes = self._get_endgame_map_biomes(endgame_map)
                for k, v in biomes.items():
                    data[k] = v

            cond = WikiCondition(
                data=data,
                cmdargs=parsed_args,
            )

            r.add_result(
                text=cond,
                out_file="area_%s.txt" % data["id"],
                wiki_page=[
                    {
                        "page": "Area:" + self._format_wiki_title(data["id"]),
                        "condition": cond,
                    },
                ],
                wiki_message="Area updater",
            )

        return r

    # =============================================================================
    # Functions
    # =============================================================================

    def _get_endgame_map_biomes(self, endgame_map):
        result = OrderedDict()

        seen = set()
        biomes = []
        adjacent_biomes = []

        for ml in endgame_map["MapLocations"]:
            # Skip duplicate map locations
            if ml["Id"] in seen:
                continue
            seen.add(ml["Id"])

            biomes.extend(b["Name"] for b in ml["Biomes"])
            adjacent_biomes.extend(b["Name"] for b in ml["AdjacentBiomes"])

        # Remove duplicate biomes
        if biomes:
            result["biomes"] = ", ".join(OrderedDict.fromkeys(biomes))
        if adjacent_biomes:
            result["adjacent_biomes"] = ", ".join(OrderedDict.fromkeys(adjacent_biomes))

        return result
