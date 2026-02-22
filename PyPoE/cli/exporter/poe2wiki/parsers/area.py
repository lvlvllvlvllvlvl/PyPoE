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
        "TN_WorldMap",
        "CharacterSelect",
        "G_login",
        "BlackTest",  # 0.3.1
        "Design",  # 0.3.1
        "Design_Lite",  # 0.3.1
        "Programming",  # 0.3.1
        "Programming_Lite",  # 0.3.1
        "G1_WorldMap",
        "G2_WorldMap",
        "G3_WorldMap",
        "G4_WorldMap",
        "G5_WorldMap",
        "G6_WorldMap",
        "G1_10",
        "G2_3s",
        "G2_8a",
        "G2_11",
        "G3_15",
        "G4_6",  # 0.3.0
        "G4_9_",  # 0.3.0
        "G4_12",  # 0.3.0
        "G4_14",  # 0.3.0
        "CurrentTown",  # 0.4.0
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
        # (
        #    "AreaType_TagsKeys",
        #    {
        #        "template": "area_type_tags",
        #        "condition": lambda v: v,
        #        "format": lambda v: ", ".join([tag["Id"] for tag in v]),
        #    },
        # ),
        (
            "Tags",
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
            "Connections",
            {
                "template": "connection_ids",
                "condition": lambda v: v,
                "format": lambda v: ", ".join(
                    OrderedDict.fromkeys(
                        [area["Id"] for area in v if area["Id"] not in AreaParser._SKIP_AREAS_BY_ID]
                    ).keys()
                ),
            },
        ),
        (
            "ParentTown",
            {
                "template": "parent_area_id",
                "condition": lambda v: v is not None,
                "format": lambda v: v["Id"],
            },
        ),
        (
            "AreaMods",
            {
                "template": "modifier_ids",
                "condition": lambda v: v,
                "format": lambda v: ", ".join([mod["Id"] for mod in v]),
            },
        ),
        (
            "Bosses",
            {
                "template": "boss_monster_ids",
                "condition": lambda v: v,
                "format": lambda v: ", ".join([mv["Id"] for mv in v]),
            },
        ),
        # (
        #    "Monsters_MonsterVarietiesKeys",
        #    {
        #        "template": "monster_ids",
        #        "condition": lambda v: v,
        #        "format": lambda v: ", ".join([mv["Id"] for mv in v]),
        #    },
        # ),
        # (
        #    "VaalArea_WorldAreasKeys",
        #    {
        #        "template": "vaal_area_ids",
        #        "condition": lambda v: v,
        #        "format": lambda v: ", ".join([a["Id"] for a in v]),
        #    },
        # ),
        # Booleans
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
        r = ExporterResult()

        if not areas:
            console(
                "No areas found for the specified parameters. Quitting.",
                msg=Msg.warning,
            )
            return r

        console("Found %s areas, parsing..." % len(areas))

        console("Accessing additional data...")
        self.rr["MapPins.dat64"].build_index("WorldAreasKeys")
        self.rr["EndgameMaps.dat64"].build_index("WorldArea")

        console("Removing disabled areas...")
        areas = [a for a in areas if a["Id"] not in self._SKIP_AREAS_BY_ID]
        areas = [a for a in areas if a["Name"] and not a["Name"].startswith("[DNT")]
        console("%s areas left. Processing..." % len(areas))

        for area in areas:
            infobox = OrderedDict()

            # Copy over simple fields from the .dat64
            parser.apply_simple_column_map(infobox, self._COPY_KEYS, area)

            # for i, (tag, value) in enumerate(
            #    zip(area["SpawnWeight_TagsKeys"], area["SpawnWeight_Values"]), start=1
            # ):
            #    infobox["spawn_weight%s_tag" % i] = tag["Id"]
            #    infobox["spawn_weight%s_value" % i] = value

            map_pin = self.rr["MapPins.dat64"].index["WorldAreasKeys"].get(area)
            if map_pin:
                infobox["flavour_text"] = map_pin[0]["FlavourText"]

            endgame_map = self.rr["EndgameMaps.dat64"].index["WorldArea"].get(area)
            if endgame_map:
                infobox["flavour_text"] = endgame_map["FlavourText"]
                get_endgame_map_biomes(infobox, endgame_map)

            if infobox.get("flavour_text"):
                infobox["flavour_text"] = parser.parse_and_handle_description_tags(
                    rr=self.rr,
                    text=infobox["flavour_text"],
                )

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


def get_endgame_map_biomes(infobox, endgame_map):
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
        infobox["biomes"] = ", ".join(OrderedDict.fromkeys(biomes))
    if adjacent_biomes:
        infobox["adjacent_biomes"] = ", ".join(OrderedDict.fromkeys(adjacent_biomes))
