"""
Wiki maps exporter

Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/wiki/parsers/maps.py                          |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Project-Path-of-Exile-Wiki                                       |
+----------+------------------------------------------------------------------+

Description
===============================================================================

Maps exporter for poewiki.net

Agreement
===============================================================================

See PyPoE/LICENSE
"""

# =============================================================================
# Imports
# =============================================================================

import os

# Python
import re
from collections import OrderedDict
import numpy as np

# 3rd-party
from PIL import Image

from PyPoE.cli.core import Msg, console
from PyPoE.cli.exporter.wiki.handler import ExporterHandler, ExporterResult
from PyPoE.cli.exporter.wiki.parsers.item import (
    WikiCondition,
    ItemsParser,
    _srgb_to_linear,
    _linear_to_srgb,
    _type_factory,
)
from PyPoE.cli.exporter.wiki.parsers.lua import LuaFormatter

# self
from PyPoE.poe import poe1constants as constants

# =============================================================================
# Classes
# =============================================================================

class MapItemWikiCondition(WikiCondition):
    NAME = "Item"

class MapsHandler(ExporterHandler):
    def __init__(self, sub_parser, *args, **kwargs):
        super().__init__(self, sub_parser, *args, **kwargs)
        self.parser = sub_parser.add_parser("maps", help="Maps exporter")
        self.parser.set_defaults(func=lambda args: self.parser.print_help())
        maps_sub = self.parser.add_subparsers()

        #
        # Maps
        #
        parser = maps_sub.add_parser("maps", help="Export maps in series")
        parser.set_defaults(func=lambda args: parser.print_help())

        self.add_default_parsers(
            parser=parser,
            cls=MapsParser,
            func=MapsParser.export_maps,
        )
        self.add_image_arguments(parser)

        parser.add_argument(
            "name",
            help="Visible name (i.e. the name you see in game). Can be specified multiple times.",
            nargs="*",
        )

        #
        # Map series (Lua)
        #
        parser = maps_sub.add_parser("map_series", help="Export map series data")

        self.add_default_parsers(
            parser=parser,
            cls=MapsParser,
            func=MapsParser.export_map_series,
        )

        #
        # Atlas data (Lua)
        #
        parser = maps_sub.add_parser("atlas", help="Export Atlas information not covered by maps")

        self.add_default_parsers(
            parser=parser,
            cls=MapsParser,
            func=MapsParser.export_atlas_nodes,
        )

        #
        # Atlas icons
        #
        parser = maps_sub.add_parser("atlas_icons", help="Export Atlas icons")

        self.add_default_parsers(
            parser=parser,
            cls=MapsParser,
            func=MapsParser.export_map_icons,
        )
        self.add_image_arguments(parser)

    def add_default_parsers(self, *args, **kwargs):
        super().add_default_parsers(*args, **kwargs)
        parser = kwargs["parser"]
        self.add_format_argument(parser)
        self.add_map_series_parsers(parser)

    def add_map_series_parsers(self, parser):
        group = parser.add_mutually_exclusive_group(required=False)
        group.add_argument(
            "-ms",
            "--map-series",
            help="Filter maps in map series by name (localized)",
            dest="map_series",
        )

        group.add_argument(
            "-msid",
            "--map-series-id",
            help="Filter maps in map series by internal ID",
            dest="map_series_id",
        )

class MapsParser(ItemsParser):

    _files = [
        "BaseItemTypes.datc64",
        "MapSeries.datc64",
    ]

    _LANG = {
        "English": {
            "Low": "Low Tier",
            "Mid": "Mid Tier",
            "High": "High Tier",
            "Uber": "Max Tier",
        },
        "German": {
            "Low": "Niedrige Stufe",
            "Mid": "Mittlere Stufe",
            "High": "Hohe Stufe",
            "Uber": "Maximale Stufe",
        },
        "Russian": {
            "Low": "низкий уровень",
            "Mid": "средний уровень",
            "High": "высокий уровень",
            "Uber": "максимальный уровень",
        },
    }

    _SKIP_ITEMS_BY_ID = {
        "Metadata/Items/Maps/MapAtlasShapersRealm",
        "Metadata/Items/Maps/MapWorldsShapersRealm",
    }

    _ITEM_SKIP_PATTERNS = dict()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    _MAP_COLORS = {
        "low tier": (248, 248, 248),
        "mid tier": (252, 159, 14),
        "high tier": (235, 3, 0),
        "purple tier": (131, 54, 231),
    }

    _MAPS_OFF_ATLAS = {
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

    _MAPS_UBER_MEMORY = {
        "Metadata/Items/Maps/MapWorldsCourtyardOfWasting",
        "Metadata/Items/Maps/MapWorldsChambersOfImpurity",
        "Metadata/Items/Maps/MapWorldsTheatreOfLies",
    }

    _MAPS_TO_SKIP_COLORING = {
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

    _MAPS_TO_SKIP_COMPOSITING = {
        "Metadata/Items/Maps/MapWorldsSynthesisedWorld",
        "Metadata/Items/Maps/MapWorldsHarbingerLow",
        "Metadata/Items/Maps/MapWorldsHarbingerMid",
        "Metadata/Items/Maps/MapWorldsHarbingerHigh",
        "Metadata/Items/Maps/MapWorldsHarbingerUber",
        "Metadata/Items/Maps/MapWorldsTrialmaster",
    }

    # This is needed because because Mercenaries series has zeroes in the
    # tier data for some maps that should not be excluded from the export.
    _MAP_SERIES_TIERS_OVERRIDE = {
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

    # TODO: Is this needed?
    def _maps_extra(self, infobox, base_item_type, map_data):
        if map_data["Shaped_AreaLevel"] > 0:
            infobox["map_area_level"] = map_data["Shaped_AreaLevel"]
        else:
            infobox["map_area_level"] = map_data["Regular_WorldAreasKey"]["AreaLevel"]

        """# Regular items are handled in the main function
        if map_data['Tier'] < 17:
            self._process_purchase_costs(
                self.rr['MapPurchaseCosts.dat64'].index['Tier'][map_data['Tier']],
                infobox
            )"""

    _type_map = _type_factory(
        data_file="Maps.dat64",
        data_mapping=(
            (
                "Tier",
                {
                    "template": "map_tier",
                },
            ),
            (
                "Regular_GuildCharacter",
                {
                    "template": "map_guild_character",
                    "condition": lambda v: v,
                },
            ),
            (
                "Regular_WorldAreasKey",
                {
                    "template": "map_area_id",
                    "format": lambda v: v["Id"],
                },
            ),
            (
                "Unique_GuildCharacter",
                {
                    "template": "unique_map_guild_character",
                    "condition": lambda v: v != "",
                },
            ),
            (
                "Unique_WorldAreasKey",
                {
                    "template": "unique_map_area_id",
                    "format": lambda v: v["Id"],
                    "condition": lambda v: v is not None,
                },
            ),
            (
                "Unique_WorldAreasKey",
                {
                    "template": "unique_map_area_level",
                    "format": lambda v: v["AreaLevel"],
                    "condition": lambda v: v is not None,
                },
            ),
        ),
        row_index=True,
        function=_maps_extra,
    )

    # TODO: Is this needed?
    def _conflict_maps(self, infobox, base_item_type, rr, language):
        id = base_item_type["Id"].replace("Metadata/Items/Maps/", "")
        # Legacy maps
        map_series = None
        for row in rr["MapSeries.dat64"]:
            if not id.startswith(row["Id"]):
                continue
            map_series = row
        # Maps are updated using the map series exporter.
        name = self._format_map_name(base_item_type)

        name_with_wonky_series = self._format_map_name(base_item_type, map_series)

        # Each iteration of maps has it's own art
        infobox["inventory_icon"] = name_with_wonky_series
        # For betrayal map conflict handling is not used, so setting this to
        # false here should be fine
        infobox["drop_enabled"] = False

        return name

    def _format_map_name(self, base_item_type, map_series=None, language=None):
        if language is None:
            language = self._language
        if "Harbinger" in base_item_type["Id"]:
            # Resolve name conflicts between Harbinger maps
            key = re.sub(r"^.*Harbinger", "", base_item_type["Id"])
            name = f"{base_item_type['Name']} ({self._LANG[language][key]})"
        else:
            name = base_item_type['Name']
        if map_series:
            name = f"{name} ({map_series['Name']})"
        return name

    def _get_map_series(self, parsed_args):
        if parsed_args.map_series_id is not None:
            self.rr["MapSeries.dat64"].build_index("Id")
            try:
                map_series = self.rr["MapSeries.dat64"].index["Id"][parsed_args.map_series_id]
            except KeyError:
                console("Invalid map series id", msg=Msg.error)
                return False
        elif parsed_args.map_series is not None:
            self.rr["MapSeries.dat64"].build_index("Name")
            try:
                map_series = self.rr["MapSeries.dat64"].index["Name"][parsed_args.map_series][0]
            except IndexError:
                console("Invalid map series name", msg=Msg.error)
                return False
        else:
            map_series = self.rr["MapSeries.dat64"][-1]
            console(
                'No map series specified. Using latest series "%s".' % (map_series["Name"],),
                msg=Msg.warning,
            )
        return map_series

    def _get_map_generation(self, series_id):
        for sid, gen in constants.MAP_SERIES_GENERATION_MAP.items():
            if series_id == sid:
                return gen
        else:
            return gen

    def _is_legacy_series(self, series_id):
        if not f"{series_id}Tier" in self.rr["MapSeriesTiers.dat64"].specification.columns_all:
            # If series is missing tier data, it's probably a legacy map series.
            # Otherwise, there's a problem with the dat spec.
            generation = self._get_map_generation(series_id)
            if generation < constants.MAP_GENERATION.WAR_FOR_THE_ATLAS:
                return True
            console(
                f"Unable to locate tier data for map series ID \"{series_id}\".",
                msg=Msg.warning,
            )
        return False

    def _get_maps_in_series(self, parsed_args, map_series):
        if "MapsKey" not in self.rr["MapSeriesTiers.dat64"].index:
            self.rr["MapSeriesTiers.dat64"].build_index("MapsKey")
        generation = self._get_map_generation(map_series["Id"])
        legacy = self._is_legacy_series(map_series["Id"])
        names = set(parsed_args.name) if "names" in parsed_args else None
        maps = []
        for map_data in self.rr["Maps.dat64"]:
            if map_data["MapGeneration"] != generation:
                continue
            if self._maybe_skip(map_data["BaseItemTypesKey"]):
                continue
            # Only include named maps, if filtering by name
            if names and map_data["BaseItemTypesKey"]["Name"] not in names:
                continue
            # T17 maps did not exist before Necropolis series
            if map_series.rowid < 22 and map_data["Tier"] == 17:
                continue
            # Uber memory maps did not exist before Mercenaries series
            if map_series.rowid < 24 and map_data["BaseItemTypesKey"]["Id"] in self._MAPS_UBER_MEMORY:
                continue
            if legacy:
                maps.append(map_data)
            elif self._get_map_series_tier(map_data, map_series) > 0:
                maps.append(map_data)
            elif map_data["BaseItemTypesKey"]["Id"] in self._MAPS_OFF_ATLAS:
                maps.append(map_data)
        return maps

    def _get_map_series_tier(self, map_data, map_series):
        tier = 0
        if map_data.rowid in self.rr["MapSeriesTiers.dat64"].index["MapsKey"]:
            if (
                map_series["Id"] in self._MAP_SERIES_TIERS_OVERRIDE
                and map_data["BaseItemTypesKey"]["Id"] in self._MAP_SERIES_TIERS_OVERRIDE[map_series["Id"]]
            ):
                tier = self._MAP_SERIES_TIERS_OVERRIDE[map_series["Id"]][map_data["BaseItemTypesKey"]["Id"]]
            else:
                map_series_tiers = self.rr["MapSeriesTiers.dat64"].index["MapsKey"][map_data.rowid]
                tier = map_series_tiers["%sTier" % map_series["Id"]]
        return tier

    def _get_map_tablet_images(self, parsed_args, map_series):
        def process(img: Image):
            img = img.crop((0, 0, 78, 78))
            return img

        tablet_image_map = {
            "Base": {
                "file": "BaseIcon_DDSFile",
                "out": "Base.dds",
            },
            "Shaper": {
                "file": "Shaper_DDSFile",
                "out": "Shaper.dds",
            },
            "Purple": {
                "file": "Purple_DDSFile",
                "out": "Tier17.dds",
            },
            "UberMemory": {
                "file": "UberMemory_DDSFile",
                "out": "UberMemory.dds",
            },
        }

        images = {}
        for name, tablet in tablet_image_map.items():
            file = map_series[tablet["file"]]
            if file:
                ico = os.path.join(self._img_path, tablet["out"])
                self._write_dds(
                    data=self.file_system.get_file(file),
                    out_path=ico,
                    parsed_args=parsed_args,
                    process=process,
                )
                img = ico.replace(".dds", ".png")
                images[name] = Image.open(img)
            else:
                images[name] = None
        return images

    def _get_map_icon_process(self, infobox, base_item, do_coloring = False, do_compositing = False, tablet_images: dict = {}):
        tier = infobox["map_tier"]
        
        def process(img: Image):
            # Recolor the map icon if appropriate and layer the map icon with the base icon.
            if do_coloring:
                color = None
                if 5 < tier <= 10:
                    color = self._MAP_COLORS["mid tier"]
                if 10 < tier:
                    color = self._MAP_COLORS["high tier"]
                if 16 < tier:
                    color = self._MAP_COLORS["purple tier"]

                # This isn't quite how the game actually makes these map icons,
                # so it isn't ideal, but it works.
                if color:
                    img = self._shade_sigil(img, color)

            if do_compositing:
                if base_item["Id"] in self._MAPS_UBER_MEMORY and tablet_images["UberMemory"]:
                    plate_img = tablet_images["UberMemory"]
                elif tier == 17 and tablet_images["Purple"]:
                    plate_img = tablet_images["Purple"]
                elif (
                    "MapShaperInfluence" in [mod["Id"] for mod in base_item["Implicit_ModsKeys"]]
                    and tablet_images["Shaper"]
                ):
                    plate_img = tablet_images["Shaper"]
                else:
                    plate_img = tablet_images["Base"]
                canvas = Image.new(plate_img.mode, plate_img.size, (0, 0, 0, 0))
                paste_origin = (
                    (plate_img.size[0] - img.size[0]) // 2,
                    (plate_img.size[1] - img.size[1]) // 2,
                )
                canvas.paste(img, paste_origin)
                img = Image.alpha_composite(plate_img, canvas)

            img = img.crop((0, 0, 78, 78))
            return img
        return process

    def _shade_sigil(self, tex, color):
        color = np.reshape(np.array(color + (255,)), (1, 1, 4)) / 255.0
        samples = np.asarray(tex, np.float32) / 255.0
        tex_colour = np.dstack((_srgb_to_linear(samples[:, :, :3]), samples[:, :, 3]))
        final = color * tex_colour
        final[:, :, :3] = _linear_to_srgb(final[:, :, :3])
        return Image.fromarray(np.uint8(final * 255.0), "RGBA")

    def export_maps(self, parsed_args):
        r = ExporterResult()

        map_series = self._get_map_series(parsed_args)
        if map_series is False:
            return r
        
        legacy = self._is_legacy_series(map_series["Id"])
        maps = self._get_maps_in_series(parsed_args, map_series)
        console(f"Processing {len(maps)} maps in {map_series['Name']} series...")

        if parsed_args.store_images:
            self._image_init(parsed_args)

            # Save off the base icons
            tablet_images = None
            if not legacy:
                if not parsed_args.convert_images or parsed_args.convert_images != ".png":
                    console(
                        "Map images need to be processed and require conversion option to be '.png'.",
                        msg=Msg.error,
                    )
                    return r
            
                tablet_images = self._get_map_tablet_images(parsed_args, map_series)

        for map_data in maps:
            base_item = map_data["BaseItemTypesKey"]
            name = self._format_map_name(base_item)
            name_series = self._format_map_name(base_item, map_series)
            tier = map_data["Tier"]
            if not legacy:
                tier = self._get_map_series_tier(map_data, map_series)

            # Base info
            infobox = OrderedDict()
            self._process_base_item_type(base_item, infobox)
            self._type_map(infobox, base_item)

            # Overrides
            infobox["map_tier"] = tier
            infobox["map_area_level"] = 67 + tier
            # Map start dropping at one tier lower, with the exception of
            # tier 1 maps which can drop rather early
            infobox["drop_level"] = 66 + tier if tier > 1 else 58
            infobox["unique_map_area_level"] = 67 + tier
            infobox["map_series"] = map_series["Name"]
            if base_item["Id"] in self._MAPS_TO_SKIP_COMPOSITING:
                infobox["inventory_icon"] = name
                icon_name = name
            else:
                infobox["map_series_icon"] = name_series
                icon_name = name_series

            if self._language != "English" and parsed_args.english_file_link:
                infobox["map_series_icon"] = self._format_map_name(
                    self.rr2["BaseItemTypes.dat64"][base_item.rowid],
                    self.rr2["MapSeries.dat64"][map_series.rowid],
                    "English",
                )

            cond = MapItemWikiCondition(
                data=infobox,
                cmdargs=parsed_args,
            )
            r.add_result(
                text=cond,
                out_file=f"map_{name}.txt",
                wiki_page=[
                    {
                        "page": name,
                        "condition": cond,
                    }
                ],
                wiki_message="Map exporter",
            )

            # Export map icon
            if parsed_args.store_images:
                dds_file_path = base_item["ItemVisualIdentityKey"]["DDSFile"]

                # Warn about map with no icon
                if not dds_file_path:
                    warnings.warn(
                        f'Missing 2d art inventory icon for "{base_item["Name"]}"'
                    )
                    continue
                
                map_ico = os.path.join(self._img_path, f"{icon_name} inventory icon.dds")
                do_coloring = not legacy and base_item["Id"] not in self._MAPS_TO_SKIP_COLORING
                do_compositing = not legacy and base_item["Id"] not in self._MAPS_TO_SKIP_COMPOSITING
                self._write_dds(
                    data=self.file_system.get_file(dds_file_path),
                    out_path=map_ico,
                    parsed_args=parsed_args,
                    process=self._get_map_icon_process(infobox, base_item, do_coloring, do_compositing, tablet_images),
                )
        
        return r

    def export_map_series(self, parsed_args):
        r = ExporterResult()

        r.add_result(
            text=LuaFormatter.format_module(
                [
                    {
                        "ordinal": i,
                        "id": tier["Id"],
                        "name": tier["Name"],
                    }
                    for i, tier in enumerate(self.rr["MapSeries.dat64"], 1)
                ]
            ),
            out_file="map_series.lua",
            wiki_page=[
                {
                    "page": "Module:Atlas/map series",
                    "condition": None,
                }
            ],
        )

        return r

    def export_atlas_nodes(self, parsed_args):
        r = ExporterResult()

        map_series = self._get_map_series(parsed_args)
        if map_series is False:
            return r
        
        legacy = self._is_legacy_series(map_series["Id"])
        if legacy:
            console(
                f"There is no additional Atlas data to export for legacy map series {map_series['Name']}.",
                msg=Msg.error,
            )
            return r

        maps = self._get_maps_in_series(parsed_args, map_series)
        latest = map_series.rowid == self.rr["MapSeries.dat64"][-1].rowid
        if not latest:
            console(
                f"{map_series['Name']} is not the latest map series. The export will not be able to include all Atlas data.",
                msg=Msg.warning,
            )
        console(f"Processing Atlas data for {len(maps)} maps in {map_series['Name']} series...")

        if "WorldAreasKey" not in self.rr["AtlasNode.dat64"].index:
            self.rr["AtlasNode.dat64"].build_index("WorldAreasKey")
        output = []
        for map_data in maps:
            for world_area in (
                map_data["Regular_WorldAreasKey"],
                map_data["Unique_WorldAreasKey"],
            ):
                if not world_area:
                    continue
                node_data = {
                    "area_id": world_area["Id"],
                    # "map_base_id": map_data["BaseItemTypesKey"]["Id"],
                    "tier_0": self._get_map_series_tier(map_data, map_series),
                }
                
                # AtlasNode.dat only contains data for latest series
                if latest:
                    try:
                        atlas_node = self.rr["AtlasNode.dat64"].index["WorldAreasKey"][world_area.rowid]
                    except KeyError:
                        continue
                    finally:
                        for n in range(5):
                            node_data[f"tier_{n}"] = atlas_node[f"Tier{n}"]
                        node_data["connections"] = [
                            conn["WorldAreasKey"]["Id"] for conn in atlas_node["AtlasNodeKeys"]
                        ]
                        node_data["is_off_atlas"] = atlas_node["NotOnAtlas"]
                        node_data["div_cards"] = [card["Id"] for card in atlas_node["DivCards"]]

                output.append(node_data)

        r.add_result(
            text=LuaFormatter.format_module(output),
            out_file="atlas_nodes_%s.lua" % map_series["Id"],
            wiki_page=[
                {
                    "page": "Module:Atlas/nodes_%s" % map_series["Id"],
                    "condition": None,
                }
            ],
        )

        return r

    def export_map_icons(self, parsed_args):
        r = ExporterResult()

        # This needs to fall back to baseitemtype -> ItemVisualIdentity.
        # It's failing on the weird Harbinger base map types and the shaper guardian maps.

        if not parsed_args.store_images or not parsed_args.convert_images:
            console(
                "Image storage options must be specified for this function",
                msg=Msg.error,
            )
            return r

        map_series = self._get_map_series(parsed_args)
        if map_series is False:
            return r

        # === Base map icons ===
        self._image_init(parsed_args)

        # output base icon (without map symbol) to .../Base.dds
        base_ico = os.path.join(self._img_path, "Base.dds")
        purple_ico = os.path.join(self._img_path, "Tier17.dds")

        # read from the file path in the BaseIcon_DDSFile field from MapSeries.dat.
        self._write_dds(
            data=self.file_system.get_file(map_series["BaseIcon_DDSFile"]),
            out_path=base_ico,
            parsed_args=parsed_args,
        )

        # read from the file path in the Purple_DDSFile field from MapSeries.dat.
        self._write_dds(
            data=self.file_system.get_file(map_series["Purple_DDSFile"]),
            out_path=purple_ico,
            parsed_args=parsed_args,
        )

        # === Maps from Atlas ===
        for atlas_node in self.rr["AtlasNode.dat64"]:
            if not atlas_node["ItemVisualIdentityKey"]["DDSFile"]:
                warnings.warn(
                    "Missing 2d art inventory icon at index %s" % atlas_node.index,
                )
                continue

            name = atlas_node["WorldAreasKey"]["Name"]

            ico = os.path.join(self._img_path, name + ".dds")

            self._write_dds(
                data=self.file_system.get_file(atlas_node["ItemVisualIdentityKey"]["DDSFile"]),
                out_path=ico,
                parsed_args=parsed_args,
            )

            if "Unique" not in atlas_node["WorldAreasKey"]["Id"]:
                ico = ico.replace(".dds", ".png")
                for name, color in self._MAP_COLORS.items():
                    ico_path = Path(ico)
                    out_path = ico_path.with_suffix(f".{name}.png")
                    if not os.path.isfile(ico_path):
                        continue

                    img = Image.open(ico_path)
                    img = self._shade_sigil(img, color)
                    img.save(out_path)

        return r
