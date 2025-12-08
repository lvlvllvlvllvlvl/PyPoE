"""
Wiki item exporter

Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/poe2wiki/parsers/item.py                      |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2 /   Project-Path-of-Exile-Wiki                          |
+----------+------------------------------------------------------------------+

Description
===============================================================================

https://poe2wiki.net

Agreement
===============================================================================

See PyPoE/LICENSE
"""

# =============================================================================
# Imports
# =============================================================================

import codecs
import os

# Python
import re
import struct
import warnings
from collections import OrderedDict
from dataclasses import dataclass
from functools import partialmethod

import matplotlib.colors
import numpy as np

# 3rd-party
from PIL import Image, ImageOps

from PyPoE.cli.core import Msg, console
from PyPoE.cli.exporter import config
from PyPoE.cli.exporter.poe2wiki import parser
from PyPoE.cli.exporter.poe2wiki.handler import ExporterHandler, ExporterResult
from PyPoE.cli.exporter.poe2wiki.parsers.skill import SkillParserShared

# Self
from PyPoE.poe import poe2constants as constants
from PyPoE.poe.file.dat import DatReader, DatRecord, RelationalReader
from PyPoE.poe.file.it import ITFile

# =============================================================================
# Functions
# =============================================================================


def log_error(msg, func):
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            warnings.warn(msg, stacklevel=2)
            raise

    return wrapped


@dataclass
class GemShadeConstants:
    hue_factor: float
    sat_factor: float
    val_factor: float
    lum_factor: float


def gemshade_constants_from_hex(hex_text: str):
    buf = codecs.decode(hex_text.replace(" ", ""), "hex")
    return GemShadeConstants(*struct.unpack("<ffff", buf))


def _srgb_to_linear(img):
    return np.piecewise(
        img,
        [img < 0.04045, img >= 0.04045],
        [lambda v: v / 12.92, lambda v: ((v + 0.055) / 1.055) ** 2.4],
    )


def _linear_to_srgb(img):
    return np.piecewise(
        img,
        [img < 0.0031308, img >= 0.0031308],
        [lambda v: v * 12.92, lambda v: 1.055 * v ** (1.0 / 2.4) - 0.055],
    )


def _apply_column_map(
    infobox, column_map: tuple[tuple[str, dict], ...], list_object: DatRecord | list[DatRecord]
):
    if not isinstance(list_object, DatRecord):
        list_object = list_object[0]

    for k, data in column_map:
        value = list_object[k]
        if data.get("condition") and not data["condition"](value):
            continue

        if data.get("format"):
            value = data["format"](value)
        infobox[data["template"]] = value


def _skip(*_):
    return False


def _type_factory(
    data_file: str,
    data_mapping: tuple[tuple[str, dict], ...],
    row_index=True,
    function=None,
    fail_condition=False,
    skip_warning=False,
    index_column="BaseItemType",
):
    def func(self, infobox, base_item_type):
        if data_file == "BaseItemTypes.dat64":
            data = base_item_type
        else:
            file: DatReader = self.rr[data_file]
            idx = base_item_type.rowid if row_index else base_item_type["Id"]

            if index_column not in file.index:
                file.build_index(index_column)

            data: DatRecord | list[DatRecord] = []
            try:
                data = file.index[index_column][idx]
            except KeyError:
                pass
            if not data:
                if not skip_warning:
                    warnings.warn(f'Missing {data_file} info for "{base_item_type["Name"]}"')
                return fail_condition
            elif not isinstance(data, DatRecord):
                # Handle missing @unique on schema column
                if len(data) == 1:
                    data = data[0]
                else:
                    raise Exception(f"Multiple matches found for {base_item_type['Id']}")

        _apply_column_map(infobox, data_mapping, data)

        if function:
            function(self, infobox, base_item_type, data)

        return True

    return log_error(f"type_factory error for {data_file}", func)


def _simple_conflict_factory(data):
    def _conflict_handler(self, infobox, base_item_type):
        appendix = data.get(base_item_type["Id"])
        if appendix is None:
            return base_item_type["Name"]
        else:
            return base_item_type["Name"] + appendix

    return _conflict_handler


def _colorize_rgba(img, black, white, mid=None, blackpoint=0, whitepoint=255, midpoint=127):
    img_a = img.getchannel("A")
    img_gray = ImageOps.grayscale(img)

    ret = ImageOps.colorize(img_gray, black, white, mid, blackpoint, whitepoint, midpoint)
    ret.putalpha(img_a)
    return ret


# =============================================================================
# Constants
# =============================================================================


SHADE_LUT: dict[(str, int), GemShadeConstants] = {
    ("str", 1): gemshade_constants_from_hex("60 E5 50 BD 6F 12 83 BD 4E 62 90 3E 08 AC 1C 3F"),
    ("str", 2): gemshade_constants_from_hex("60 E5 50 BE B6 F3 7D 3E 33 33 B3 BE BA 49 4C 3F"),
    ("dex", 1): gemshade_constants_from_hex("9A 99 19 BE F4 FD 54 BD D1 22 5B 3E F0 A7 46 3F"),
    ("dex", 2): gemshade_constants_from_hex("B8 1E 85 3E 0A D7 A3 3D 19 04 16 BF 23 DB 39 3F"),
    ("int", 1): gemshade_constants_from_hex("AE 47 E1 BD AE 47 61 BE 0A D7 23 BD 00 00 80 3F"),
    ("int", 2): gemshade_constants_from_hex("8F C2 75 3D 0A D7 23 3D 0A D7 A3 BD 00 00 80 3F"),
}


# =============================================================================
# Classes
# =============================================================================


class WikiCondition(parser.WikiCondition):
    COPY_KEYS = (
        # for skills
        "radius",
        "radius_description",
        "radius_secondary",
        "radius_secondary_description",
        "radius_tertiary",
        "radius_tertiary_description",
        # all items
        "name_list",
        "quality",
        # Icons & Visuals
        "inventory_icon",
        "alternate_art_inventory_icons",
        "frame_type",
        "influences",
        "card_background",
        "skill_icon",
        # Drop restrictions
        "drop_enabled",
        "acquisition_tags",
        "drop_areas",
        "drop_text",
        "drop_monsters",
        "is_drop_restricted",
        "drop_level_maximum",
        "drop_rarities_ids",
        # Item flags
        "is_corrupted",
        "is_mirrored",
        "is_fractured",
        "is_synthesised",
        "is_searing_exarch_item",
        "is_eater_of_worlds_item",
        "is_veiled",
        "is_replica",
        "can_not_be_traded_or_modified",
        "is_sellable",
        "is_in_game",
        "is_unmodifiable",
        "is_account_bound",
        "suppress_improper_modifiers_category",
        "disable_automatic_recipes",
        # MTX Categorization
        "cosmetic_type",
        # Version information
        "release_version",
        "removal_version",
        # Quest Rewards
        "quest_reward1_type",
        "quest_reward1_quest",
        "quest_reward1_quest_id",
        "quest_reward1_act",
        "quest_reward1_class_ids",
        "quest_reward1_npc",
        "quest_reward2_type",
        "quest_reward2_quest",
        "quest_reward2_quest_id",
        "quest_reward2_act",
        "quest_reward2_class_ids",
        "quest_reward2_npc",
        "quest_reward3_type",
        "quest_reward3_quest",
        "quest_reward3_quest_id",
        "quest_reward3_act",
        "quest_reward3_class_ids",
        "quest_reward3_npc",
        "quest_reward4_type",
        "quest_reward4_quest",
        "quest_reward4_quest_id",
        "quest_reward4_act",
        "quest_reward4_class_ids",
        "quest_reward4_npc",
    )
    COPY_MATCH = re.compile(
        r"^(recipe|sell_price|inherent_skill[0-9]+_(?:min|max)_level|implicit[0-9]+_(?:text|random_list)).*",
        re.UNICODE,
    )

    NAME = "Item"
    INDENT = 40
    ADD_INCLUDE = False


class ItemWikiCondition(WikiCondition):
    NAME = "Item"


class ItemsHandler(ExporterHandler):
    def __init__(self, sub_parser, *args, **kwargs):
        super().__init__(self, sub_parser, *args, **kwargs)
        self.parser = sub_parser.add_parser("items", help="Items Exporter")
        self.parser.set_defaults(func=lambda args: self.parser.print_help())
        core_sub = self.parser.add_subparsers()

        #
        # Generic base item export
        #
        item_parser = core_sub.add_parser("item", help="Regular item export")
        item_parser.set_defaults(func=lambda args: parser.print_help())
        sub = item_parser.add_subparsers()

        self.add_default_subparser_filters(sub, cls=ItemsParser, type="item")

        item_filter_parser = sub.add_parser(
            "by_filter",
            help="Extracts all items matching various filters",
        )

        self.add_default_parsers(
            parser=item_filter_parser,
            cls=ItemsParser,
            func=ItemsParser.by_filter,
            type="item",
        )
        item_filter_parser.add_argument(
            "-ft-n",
            "--filter-name",
            help="Filter by item name using regular expression.",
            dest="re_name",
        )

        item_filter_parser.add_argument(
            "-ft-id",
            "--filter-id",
            "--filter-metadata-id",
            help="Filter by item metadata id using regular expression",
            dest="re_id",
        )

    def add_default_parsers(self, *args, type=None, **kwargs):
        super().add_default_parsers(*args, **kwargs)
        parser = kwargs["parser"]
        self.add_format_argument(parser)
        parser.add_argument(
            "--disable-english-file-links",
            help="Disables putting english file links in inventory icon for non English languages",
            action="store_false",
            dest="english_file_link",
            default=True,
        )
        kwargs["parser"].add_argument(
            "--omit-skill-data",
            action="store_true",
            help="Don't export skill data for gem items.",
            dest="omit_skill_data",
        )

        if type == "item":
            parser.add_argument(
                "-ft-c",
                "--filter-class",
                help="Filter by item class(es). Case sensitive.",
                nargs="*",
                dest="item_class",
            )

            parser.add_argument(
                "-ft-cid",
                "--filter-class-id",
                help="Filter by item class id(s). Case sensitive.",
                nargs="*",
                dest="item_class_id",
            )

            self.add_image_arguments(parser)
        elif type == "prophecy":
            parser.add_argument(
                "--allow-disabled",
                help="Allows disabled prophecies to be exported",
                action="store_true",
                dest="allow_disabled",
                default=False,
            )


class ItemsParser(SkillParserShared):
    _regex_format = re.compile(r"(?P<index>x|y|z)" r"(?:[\W]*)" r"(?P<tag>%|second)", re.IGNORECASE)

    # Core files we need to load
    _files = [
        "BaseItemTypes.datc64",
    ]

    # Core translations we need
    _translations = [
        "stat_descriptions.txt",
        "gem_stat_descriptions.txt",
        "skill_stat_descriptions.txt",
        "active_skill_gem_stat_descriptions.txt",
    ]

    _item_column_index_filter = partialmethod(
        SkillParserShared._column_index_filter,
        dat_file_name="BaseItemTypes.dat64",
        error_msg="Several items have not been found:\n%s",
    )

    # Item inventory icons are scaled down so that this is the largest dimension
    _ICON_MAX_DIMENSION = 420

    _IGNORE_DROP_LEVEL_CLASSES = (
        "Active Skill Gem",
        "Meta Skill Gem",
        "HideoutDoodad",
        "Microtransaction",
        "InstanceLocalItem",
    )

    _DROP_DISABLED_ITEMS_BY_ID = {}

    # For some reason these items have different drop level in game and in BaseItemTypes.dat
    _DROP_LEVEL_BY_ID = {
        # =================================================================
        # Amulets
        # =================================================================
        "Metadata/Items/Amulets/FourAmulet8": 22,
        # =================================================================
        # Sceptres
        # =================================================================
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre6a": 24,
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre6b": 24,
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre6c": 24,
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptreUnique1": 24,
    }

    _REQUIRED_LEVEL_BY_ID = {
        # =================================================================
        # Amulets
        # =================================================================
        "Metadata/Items/Amulets/FourAmulet8": 24,
        # =================================================================
        # Staves
        # =================================================================
        "Metadata/Items/Weapons/TwoHandWeapons/Staves/FourStaff3": 1,
    }

    _FORCE_INVENTORY_ICON_BY_ID = {
        # =================================================================
        # Skill Gems
        # =================================================================
        # Ascendancy granted
        "Metadata/Items/Gem/SkillGemAscendancyAncestralSpirits": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyBleedingConcoction": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyBloodBoil": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyDemonForm": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyElementalExpression": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyElementalStorm": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyEncasedInJade": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyExplosiveConcoction": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyFireSpellOnHit": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyFulminatingConcoction": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyInfuseWeapon": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyIntoTheBreach": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyLifeRemnants": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyManifestWeapon": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyMeditate": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyPoisonousConcoction": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyRitualSacrifice": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyShatteringConcoction": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancySorceryWard": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancySummonInfernalHound": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancySupportingFire": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyTemperWeapon": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyTemporalRift": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyTimeFreeze": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyTimeSnap": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyUnboundAvatar": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyUnleash": "Ascendancy",
        "Metadata/Items/Gem/SkillGemTriggeredAbyssalApparition": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendanyMetaDeadeyeMarks": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyInevitableAgony": "Ascendancy",
        "Metadata/Items/Gem/SkillGemAscendancyTemperWeapon": "Ascendancy",
        # Item granted
        "Metadata/Items/Gem/SkillGemBoneBlast": "Item",
        "Metadata/Items/Gems/SkillGemCastOnBlock": "Item",
        "Metadata/Items/Gems/SkillGemCastOnCharmUse": "Item",
        "Metadata/Items/Gems/SkillGemChaosbolt": "Item",
        "Metadata/Items/Gem/SkillGemChaoticInfusion": "Item",
        "Metadata/Items/Gems/SkillGemCorpseCloud": "Item",
        "Metadata/Items/Gems/SkillGemDiscipline": "Item",
        "Metadata/Items/Gems/SkillGemFirebolt": "Item",
        "Metadata/Items/Gems/SkillGemFreezingShards": "Item",
        "Metadata/Items/Gems/SkillGemLightningSpellOnHit": "Item",
        "Metadata/Items/Gem/SkillGemMalice": "Item",
        "Metadata/Items/Gem/SkillGemManaDrain": "Item",
        "Metadata/Items/Gem/SkillGemParry": "Item",
        "Metadata/Items/Gems/SkillGemPowerSiphon": "Item",
        "Metadata/Items/Gems/SkillGemPurityOfFire": "Item",
        "Metadata/Items/Gems/SkillGemPurityOfIce": "Item",
        "Metadata/Items/Gems/SkillGemPurityOfLightning": "Item",
        "Metadata/Items/Gem/SkillGemShieldBlock": "Item",
        "Metadata/Items/Gems/SkillGemSigilOfPower": "Item",
        "Metadata/Items/Gems/SkillGemSkeletalWarriorWeaponSkill": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultSpearThrow": "Item",
        "Metadata/Items/Gems/SkillGemVolatileDead": "Item",
        "Metadata/items/Gems/SkillGemStaffUnleash": "Item",
        "Metadata/Items/Gem/SkillGemBlinkSandPlayer": "Item",
        "Metadata/Items/Gem/SkillGemUniqueBreachLightningBolt": "Item",
        "Metadata/Items/Gems/SkillGemLightningBolt": "Item",
        "Metadata/Items/Gem/SkillGemSolarOrb": "Item",
        "Metadata/items/Gems/SkillGemStaffConsecrate": "Item",
        "Metadata/Items/Gems/SkillGemHisFoulEmergence": "Item",
        "Metadata/Items/Gems/SkillGemVileDisruption": "Item",
        "Metadata/Items/Gems/SkillGemScatteringCalamity": "Item",
        "Metadata/Items/Gems/SkillGemHisWinnowingFlame": "Item",
        "Metadata/Items/Gem/SkillGemCrossbowRequiem": "Item",
        "Metadata/Items/Gem/SkillGemSpellslinger": "Item",
        "Metadata/Items/Gem/SkillGemGeminiSurge": "Item",
        "Metadata/Items/Gems/SkillGemValakosCharge": "Item",
        "Metadata/Items/Gem/SkillGemPhantasmalArrow": "Item",
        "Metadata/Items/Gems/SkillGemCracklingPalm": "Item",
        "Metadata/Items/Gems/SkillGemEnervatingNova": "Item",
        "Metadata/Items/Gem/SkillGemFeastOfFlesh": "Item",
        "Metadata/Items/Gem/SkillGemFulmination": "Item",
        "Metadata/Items/Gems/SkillGemFuturePast": "Item",
        "Metadata/Items/Gems/SkillGemGalvanicField": "Item",
        "Metadata/Items/Gems/SkillGemImpurity": "Item",
        "Metadata/Items/Gem/SkillGemPinnacleOfPower": "Item",
        # Weapon default attacks
        "Metadata/Items/Gem/SkillGemPlayerDefault1HAxe": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefault2HAxe": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultAxeAxe": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefault1HSword": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefault2HSword": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultSwordSword": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefault1HMace": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefault2HMace": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultMaceMace": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultQuarterstaff": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultFlail": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultUnarmed": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultBow": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultCrossbow": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultSpear": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultDagger": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultDaggerDagger": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultClaw": "Item",
        "Metadata/Items/Gem/SkillGemPlayerDefaultClawClaw": "Item",
        # =================================================================
        # Body armours
        # =================================================================
        "Metadata/Items/Armours/BodyArmours/FourBodyStrDex4aEndgame": "Cloaked Mail",
        "Metadata/Items/Armours/BodyArmours/FourBodyStrDex4bEndgame": "Cloaked Mail",
        "Metadata/Items/Armours/BodyArmours/FourBodyStrDex4cEndgame": "Cloaked Mail",
        # =================================================================
        # Gloves
        # =================================================================
        "Metadata/Items/Armours/Gloves/FourGlovesInt3Cruel": "Stitched Gloves",
        "Metadata/Items/Armours/Gloves/FourGlovesInt7": "Leopold's Applause",
        # =================================================================
        # Bucklers
        # =================================================================
        "Metadata/Items/Armours/Shields/FourShieldDex3Endgame": "Plated Buckler",
        "Metadata/Items/Armours/Shields/FourShieldDex11": "Ornate Buckler",
        # =================================================================
        # Quest items
        # =================================================================
        "Metadata/Items/QuestItems/Gallows/Act1/CrowbellSkillBook": "Book of Specialisation",
        "Metadata/Items/QuestItems/Gallows/Act1/UnaSkillBook": "Book of Specialisation",
        "Metadata/Items/QuestItems/Gallows/Act2/SerpentClanCasterBossDrop": "Book of Specialisation",
        "Metadata/Items/QuestItems/Gallows/Act2/FinalLetterSkillBook": "Book of Specialisation",
        "Metadata/Items/QuestItems/Gallows/Act3/QuadrillaSkillBook": "Book of Specialisation",
        "Metadata/Items/QuestItems/Gallows/Act4/BlindBeastSkillBook": "Book of Specialisation",
        "Metadata/Items/QuestItems/Gallows/Interlude/FrozenPrisonerSkillBook": "Book of Specialisation",
        "Metadata/Items/QuestItems/Gallows/Interlude/IceTusksSkillBook": "Book of Specialisation",
        "Metadata/Items/QuestItems/Gallows/Interlude/InterludePart2SkillBook": "Book of Specialisation",
        "Metadata/Items/QuestItems/Gallows/Interlude/InterludeFinalSkillBook": "Book of Specialisation",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric1": "Crystalline Core of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric3": "Crystalline Core of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric6": "Crystalline Core of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric9": "Crystalline Core of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric12": "Crystalline Core of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric15": "Crystalline Core of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookUniqueMaps1": "Book of Unique Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookUniqueMaps2": "Book of Unique Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookUniqueMaps3": "Book of Unique Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookUniqueMaps4": "Book of Unique Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookUniqueMaps5": "Book of Unique Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookPinnacle1": "Arbiter's Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookPinnacle2": "Arbiter's Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookPinnacle3": "Arbiter's Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookPinnacle4": "Arbiter's Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBreach1": "Otherworldly Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBreach2": "Otherworldly Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBreach3": "Otherworldly Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBreach4": "Otherworldly Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookDelirium1": "Deranging Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookDelirium2": "Deranging Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookDelirium3": "Deranging Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookDelirium4": "Deranging Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookRitual1": "Ritualistic Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookRitual2": "Ritualistic Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookRitual3": "Ritualistic Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookRitual4": "Ritualistic Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookExpedition1": "Runic Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookExpedition2": "Runic Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookExpedition3": "Runic Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookExpedition4": "Runic Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBoss1": "Vanquisher's Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBoss2": "Vanquisher's Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBoss3": "Vanquisher's Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBoss4": "Vanquisher's Book of Knowledge",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBoss5": "Vanquisher's Book of Knowledge",
        "Metadata/Items/QuestItems/Gallows/Act1/ManorGargoyleDropCruel": "Candlemass' Essence",
        "Metadata/Items/QuestItems/Gallows/Act3/GoldIdol4": "Golden Idol",
        "Metadata/Items/QuestItems/Gallows/Act3/GoldIdol5": "Grand Idol",
        "Metadata/Items/QuestItems/Gallows/Act3/GoldIdol6": "Glorious Idol",
        "Metadata/Items/QuestItems/Gallows/Act3/SnakeLadyPotionConsumable4": "Venom Draught of Stone",
        "Metadata/Items/QuestItems/Gallows/Act3/SnakeLadyPotionConsumable5": "Venom Draught of the Veil",
        "Metadata/Items/QuestItems/Gallows/Act3/SnakeLadyPotionConsumable6": "Venom Draught of Clarity",
        # =================================================================
        # Misc
        # =================================================================
        "Metadata/Items/TowerAugment/GenericAugment": "Precursor Tablet",
    }

    _NAME_OVERRIDE_BY_ID = {"English": {}}

    # Override also name in infobox (temporary, maybe)
    _NAME_OVERRIDE_BY_ID_2 = {
        "English": {
            # =================================================================
            # Skill Gems
            # =================================================================
            "Metadata/Items/Gem/SupportGemLivingLightning": "Living Lightning I",
            # =================================================================
            # Quest Items
            # =================================================================
            "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric1": "Crystalline Core of Knowledge",
            "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookUniqueMaps1": "Book of Unique Knowledge",
            "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookPinnacle1": "Arbiter's Book of Knowledge",
            "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBreach1": "Otherworldly Book of Knowledge",
            "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookDelirium1": "Deranging Book of Knowledge",
            "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookRitual1": "Ritualistic Book of Knowledge",
            "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookExpedition1": "Runic Book of Knowledge",
            "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBoss1": "Vanquisher's Book of Knowledge",
            # =================================================================
            # Uncut Gems
            # =================================================================
            "Metadata/Items/Gems/SkillGemUncut1": "Uncut Skill Gem",
            "Metadata/Items/Gems/SupportGemUncut1": "Uncut Support Gem",
            "Metadata/Items/Gems/ReservationGemUncut4": "Uncut Spirit Gem",
            "Metadata/Items/Gems/SkillGemUncutQuest1": "Uncut Skill Gem",
        }
    }

    _NAME_APPENDIX_BY_ID = {
        "English": {
            # =================================================================
            # Skill Gems
            # =================================================================
            "Metadata/Items/Gem/SkillGemAscendancyUnleash": " (Chronomancer skill)",
            "Metadata/items/Gems/SkillGemStaffUnleash": " (skill)",
            "Metadata/Items/Gems/SkillGemFlammability": " (curse)",
            "Metadata/Items/Gem/SkillGemUniqueBreachLightningBolt": " (triggered skill)",
            "Metadata/Items/Gems/SkillGemLightningBolt": "",
            "Metadata/Items/Gem/SkillGemBlinkSandPlayer": " (Sands of Silk)",
            "Metadata/Items/Gem/SkillGemBlink": "",
            # Weapon attacks
            "Metadata/Items/Gem/SkillGemPlayerDefault1HAxe": " (one hand)",
            "Metadata/Items/Gem/SkillGemPlayerDefault2HAxe": " (two hand)",
            "Metadata/Items/Gem/SkillGemPlayerDefaultAxeAxe": " (dual wield)",
            "Metadata/Items/Gem/SkillGemPlayerDefault1HSword": " (one hand)",
            "Metadata/Items/Gem/SkillGemPlayerDefault2HSword": " (two hand)",
            "Metadata/Items/Gem/SkillGemPlayerDefaultSwordSword": " (dual wield)",
            "Metadata/Items/Gem/SkillGemPlayerDefault1HMace": " (one hand)",
            "Metadata/Items/Gem/SkillGemPlayerDefault2HMace": " (two hand)",
            "Metadata/Items/Gem/SkillGemPlayerDefaultMaceMace": " (dual wield)",
            "Metadata/Items/Gem/SkillGemPlayerDefaultSpear": "",
            "Metadata/Items/Gem/SkillGemPlayerDefaultDagger": "",
            "Metadata/Items/Gem/SkillGemPlayerDefaultDaggerDagger": " (dual wield)",
            "Metadata/Items/Gem/SkillGemPlayerDefaultClaw": "",
            "Metadata/Items/Gem/SkillGemPlayerDefaultClawClaw": " (dual wield)",
            # =================================================================
            # Support Gems
            # =================================================================
            "Metadata/Items/Gems/SupportGemArcaneSurge": " (support gem)",
            "Metadata/Items/Gems/SupportGemElectrocute": " (support gem)",
            "Metadata/Items/Gems/SupportGemFork": " (support gem)",
            "Metadata/Items/Gems/SupportGemGlaciation": " (support gem)",
            "Metadata/Items/Gem/SupportGemHinder": " (support gem)",
            "Metadata/Items/Gem/SupportGemImpale": " (support gem)",
            "Metadata/Items/Gems/SupportGemBludgeon": " (support gem)",
            "Metadata/Items/Gems/SupportGemMaim": " (support gem)",
            "Metadata/Items/Gems/SupportGemConduction": " (support gem)",
            "Metadata/Items/Gem/SupportGemVolatility": " (support gem)",
            "Metadata/Items/Gems/SupportGemUnleash": "",
            # =================================================================
            # Uncut Gems
            # =================================================================
            "Metadata/Items/Gems/SkillGemUncutQuest1": " (quest item)",
            # =================================================================
            # Body armours
            # =================================================================
            "Metadata/Items/Armours/BodyArmours/FourBodyStrDex4aEndgame": " (Fire)",
            "Metadata/Items/Armours/BodyArmours/FourBodyStrDex4bEndgame": " (Cold)",
            "Metadata/Items/Armours/BodyArmours/FourBodyStrDex4cEndgame": " (Lightning)",
            "Metadata/Items/Armours/BodyArmours/FourBodyStrDex12a": " (Fire)",
            "Metadata/Items/Armours/BodyArmours/FourBodyStrDex12b": " (Cold)",
            "Metadata/Items/Armours/BodyArmours/FourBodyStrDex12c": " (Lightning)",
            # =================================================================
            # Gloves
            # =================================================================
            # =================================================================
            # Bucklers
            # =================================================================
            # Ornate
            "Metadata/Items/Armours/Shields/FourShieldDex3Endgame": "",
            "Metadata/Items/Armours/Shields/FourShieldDex11": " (unique only)",
            # =================================================================
            # Sceptres
            # =================================================================
            "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre6a": " (Fire)",
            "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre6b": " (Cold)",
            "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre6c": " (Lightning)",
            "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptreUnique1": " (base type)",
            # =================================================================
            # Rings
            # =================================================================
            "Metadata/Items/Rings/FourRingBase": " (base type)",
            # =================================================================
            # Tablets
            # =================================================================
            "Metadata/Items/TowerAugment/GenericAugment": " (generic)",
            # =================================================================
            # Quest items
            # =================================================================
            "Metadata/Items/QuestItems/Gallows/Act1/CrowbellSkillBook": " (The Crowbell)",
            "Metadata/Items/QuestItems/Gallows/Act1/UnaSkillBook": " (The Lost Lute)",
            "Metadata/Items/QuestItems/Gallows/Act2/SerpentClanCasterBossDrop": " (Kabala, Constrictor Queen)",
            "Metadata/Items/QuestItems/Gallows/Act2/FinalLetterSkillBook": " (Tradition's Toll)",
            "Metadata/Items/QuestItems/Gallows/Act3/QuadrillaSkillBook": " (Mighty Silverfist)",
            "Metadata/Items/QuestItems/Gallows/Interlude/IceTusksSkillBook": " (Howling Winds)",
            "Metadata/Items/QuestItems/Gallows/Interlude/InterludePart2SkillBook": " (Clearing the Way)",
            "Metadata/Items/QuestItems/Gallows/Interlude/InterludeFinalSkillBook": " (Interlude)",
            "Metadata/Items/QuestItems/Gallows/Act1/ManorGargoyleDrop": "",
            "Metadata/Items/QuestItems/Gallows/Act1/ManorGargoyleDropCruel": " (Cruel)",
            # =================================================================
            # Hideout decorations
            # =================================================================
            "Metadata/Items/Hideout/HideoutLightningCoil": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutVollConfession": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutRaptureDevice": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutBeastLoreObject": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutEncampmentLetters": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutPrisonTorturedevice8": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutColossusSword": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutChestVaal": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutIncaPyramid": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutRitualTotem": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutCharredSkeleton": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutVaalWhispySmoke": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutLionStatueKneeling": "",  # Sitting Lion Statue
            "Metadata/Items/Hideout/HideoutChurchRuins": " (hideout decoration)",
            "Metadata/Items/Hideout/HideoutIncaLetter": " (hideout decoration)",
            # =================================================================
            # Cosmetic items
            # =================================================================
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x1": " (1x1)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x2": " (1x2)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x3": " (1x3)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x4": " (1x4)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x1": " (2x1)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x2": " (2x2)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x3": " (2x3)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x4": " (2x4)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox3x2": " (3x2)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox3x3": " (3x3)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionIronMaiden": " (helmet skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionInfernalAxe": " (weapon skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionColossusSword": "",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionLegionBoots": " (boots skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionLegionGloves": " (gloves skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionScholarBoots": " (boots skin)",
            "Metadata/Items/Pets/DemonLion": " (pet)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionHoodedCloak": " (armour attachment)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionArcaneCloak": " (armour attachment)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCrusaderHelmet": " (helmet skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCrusaderBoots": " (boots skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCrusaderGloves": " (gloves skin)",
            "Metadata/Items/MicrotransactionCurrency/StashTab": " (consumable item)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemigodsAuthority": " (weapon skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemigodsBeacon": " (shield skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemigodsBounty": " (belt skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemigodsDominance": " (armour skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemigodsEye": " (ring skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemigodsImmortality": " (helmet skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemigodsPresence": " (amulet skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemigodsStride": " (boots skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemigodsTouch": " (gloves skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemigodsTriumph": " (helmet skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionWarlockGloves": " (gloves skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionWarlockBoots": " (boots skin)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionConquestHelmet": " (helmet skin)",
        },
        "Russian": {
            # =================================================================
            # Active Skill Gems
            # =================================================================
            "Metadata/Items/Gems/SkillGemPortal": " (камень умения)",
            # =================================================================
            # One Hand Axes
            # =================================================================
            "Metadata/Items/Weapons/OneHandWeapons/OneHandAxes/OneHandAxe22": "",
            # =================================================================
            # Boots
            # =================================================================
            "Metadata/Items/Armours/Boots/BootsInt4": "",
            # Legion Boots
            "Metadata/Items/Armours/Boots/BootsStrInt7": "",
            "Metadata/Items/Armours/Boots/BootsAtlas1": " (сопротивление холоду и молнии)",
            "Metadata/Items/Armours/Boots/BootsAtlas2": " (сопротивление огню и холоду)",
            "Metadata/Items/Armours/Boots/BootsAtlas3": " (сопротивление огню и молнии)",
            # =================================================================
            # Gloves
            # =================================================================
            # Legion Gloves
            "Metadata/Items/Armours/Gloves/GlovesStrInt7": "",
            # =================================================================
            # Quivers
            # =================================================================
            "Metadata/Items/Quivers/QuiverDescent": " (Спуск)",
            # =================================================================
            # Rings
            # =================================================================
            "Metadata/Items/Rings/Ring12": " (рубин и топаз)",
            "Metadata/Items/Rings/Ring13": " (сапфир и топаз)",
            "Metadata/Items/Rings/Ring14": " (рубин и сапфир)",
            # =================================================================
            # Amulets
            # =================================================================
            "Metadata/Items/Amulets/Talismans/Talisman2_6_1": (
                " (получаемый урон от огня становится уроном от холода)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman2_6_2": (
                " (получаемый урон от огня становится уроном от молнии)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman2_6_3": (
                " (получаемый урон от холода становится уроном от огня)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman2_6_4": (
                " (получаемый урон от холода становится уроном от молнии)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman2_6_5": (
                " (получаемый урон от молнии становится уроном от холода)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman2_6_6": (
                " (получаемый урон от молнии становится уроном от огня)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman3_6_1": " (заряд энергии при убийстве)",
            "Metadata/Items/Amulets/Talismans/Talisman3_6_2": " (заряд ярости при убийстве)",
            "Metadata/Items/Amulets/Talismans/Talisman3_6_3": " (заряд выносливости при убийстве)",
            # =================================================================
            # Hideout Doodads
            # =================================================================
            "Metadata/Items/Hideout/HideoutMalachaiHeart": " (предмет убежища)",
            "Metadata/Items/Hideout/HideoutVaalWhispySmoke": " (предмет убежища)",
            "Metadata/Items/Hideout/HideoutChestVaal": " (предмет убежища)",
            "Metadata/Items/Hideout/HideoutEncampmentFireplace": " (предмет убежища)",
            "Metadata/Items/Hideout/HideoutEncampmentLetters": " (предмет убежища)",
            "Metadata/Items/Hideout/HideoutIncaPyramid": " (предмет убежища)",
            "Metadata/Items/Hideout/HideoutDarkSoulercoaster": " (предмет убежища)",
            "Metadata/Items/Hideout/HideoutVaalMechanism": " (предмет убежища)",
            "Metadata/Items/Hideout/HideoutCharredSkeleton": " (предмет убежища)",
            "Metadata/Items/HideoutInteractables/DexIntCraftingBench": " (предмет убежища)",
            # =================================================================
            # Piece
            # =================================================================
            "Metadata/Items/UniqueFragments/FragmentUniqueShield1_1": " (1 из 4)",
            "Metadata/Items/UniqueFragments/FragmentUniqueShield1_2": " (2 из 4)",
            "Metadata/Items/UniqueFragments/FragmentUniqueShield1_3": " (3 из 4)",
            "Metadata/Items/UniqueFragments/FragmentUniqueShield1_4": " (4 из 4)",
            "Metadata/Items/UniqueFragments/FragmentUniqueSword1_1": " (1 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueSword1_2": " (2 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueSword1_3": " (3 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueStaff1_1": " (1 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueStaff1_2": " (2 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueStaff1_3": " (3 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueBelt1_1": " (1 из 2)",
            "Metadata/Items/UniqueFragments/FragmentUniqueBelt1_2": " (2 из 2)",
            "Metadata/Items/UniqueFragments/FragmentUniqueQuiver1_1": " (1 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueQuiver1_2": " (2 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueQuiver1_3": " (3 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueHelmet1_1": " (1 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueHelmet1_2": " (2 из 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueHelmet1_3": " (3 из 3)",
            # =================================================================
            # MTX
            # =================================================================
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x1": " (1x1)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x2": " (1x2)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x3": " (1x3)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x4": " (1x4)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x1": " (2x1)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x2": " (2x2)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x3": " (2x3)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x4": " (2x4)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox3x2": " (3x2)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox3x3": " (3x3)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionIronMaiden": "",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionInfernalAxe": (
                " (внешний вид оружия)"
            ),
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionColossusSword": "",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionLegionBoots": (
                " (микротранзакция)"
            ),
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionLegionGloves": (
                " (микротранзакция)"
            ),
            "Metadata/Items/MicrotransactionItemEffects/MasterArmour1Boots": " (микротранзакция)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSinFootprintsEffect": (
                " (микротранзакция)"
            ),
            "Metadata/Items/Pets/DemonLion": " (питомец)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionHeartWeapon2014": " (2014)",
            # =================================================================
            # Quest items
            # =================================================================
            "Metadata/Items/QuestItems/GoldenPages/Page1": " (1 из 4)",
            "Metadata/Items/QuestItems/GoldenPages/Page2": " (2 из 4)",
            "Metadata/Items/QuestItems/GoldenPages/Page3": " (3 из 4)",
            "Metadata/Items/QuestItems/GoldenPages/Page4": " (4 из 4)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier8_1": " (1 из 2)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier8_2": " (2 из 2)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier9_1": " (1 из 3)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier9_2": " (2 из 3)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier9_3": " (3 из 3)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier10_1": " (1 из 3)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier10_2": " (2 из 3)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier10_3": " (3 из 3)",
            "Metadata/Items/QuestItems/RibbonSpool": " (предмет)",
            "Metadata/Items/QuestItems/Act7/SilverLocket": " (предмет)",
            "Metadata/Items/QuestItems/Act7/KisharaStar": " (предмет)",
            "Metadata/Items/QuestItems/Act8/WingsOfVastiri": " (предмет)",
            "Metadata/Items/QuestItems/Act9/StormSword": " (предмет)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_1": " (1 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_2": " (2 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_3": " (3 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_4": " (4 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_5": " (5 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_6": " (6 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_7": " (7 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_8": " (8 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_1": " (1 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_2": " (2 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_3": " (3 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_4": " (4 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_5": " (5 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_6": " (6 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_7": " (7 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_8": " (8 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_1": " (1 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_2": " (2 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_3": " (3 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_4": " (4 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_5": " (5 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_6": " (6 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_7": " (7 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_8": " (8 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_1": " (1 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_2": " (2 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_3": " (3 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_4": " (4 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_5": " (5 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_6": " (6 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_7": " (7 из 8)",
            "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_8": " (8 из 8)",
        },
        "German": {
            # =================================================================
            # One Hand Axes
            # =================================================================
            "Metadata/Items/Weapons/OneHandWeapons/OneHandAxes/OneHandAxe22": "",
            # =================================================================
            # Boots
            # =================================================================
            "Metadata/Items/Armours/Boots/BootsInt4": "",
            # Legion Boots
            "Metadata/Items/Armours/Boots/BootsStrInt7": "",
            "Metadata/Items/Armours/Boots/BootsAtlas1": " (Kälte und Blitz Resistenzen)",
            "Metadata/Items/Armours/Boots/BootsAtlas2": " (Feuer und Kälte Resistenzen)",
            "Metadata/Items/Armours/Boots/BootsAtlas3": " (Feuer und Blitz Resistenzen)",
            # =================================================================
            # Gloves
            # =================================================================
            # Legion Gloves
            "Metadata/Items/Armours/Gloves/GlovesStrInt7": "",
            # =================================================================
            # Quivers
            # =================================================================
            "Metadata/Items/Quivers/QuiverDescent": " (Descent)",
            # =================================================================
            # Rings
            # =================================================================
            "Metadata/Items/Rings/Ring12": " (Rubin und Topas)",
            "Metadata/Items/Rings/Ring13": " (Saphir und Topas)",
            "Metadata/Items/Rings/Ring14": " (Rubin und Saphir)",
            # =================================================================
            # Amulets
            # =================================================================
            "Metadata/Items/Amulets/Talismans/Talisman2_6_1": (
                " (Feuerschaden erlitten als Kälteschaden)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman2_6_2": (
                " (Feuerschaden erlitten als Blitzschaden)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman2_6_3": (
                " (Kälteschaden erlitten als Feuerschaden)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman2_6_4": (
                " (Kälteschaden erlitten als Blitzschaden)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman2_6_5": (
                " (Blitzschaden erlitten als Kälteschaden)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman2_6_6": (
                " (Blitzschaden erlitten als Feuerschaden)"
            ),
            "Metadata/Items/Amulets/Talismans/Talisman3_6_1": " (Energie-Ladung bei Tötung)",
            "Metadata/Items/Amulets/Talismans/Talisman3_6_2": " (Raserei-Ladung bei Tötung)",
            "Metadata/Items/Amulets/Talismans/Talisman3_6_3": " (Widerstands-Ladung bei Tötung)",
            # =================================================================
            # Hideout Doodads
            # =================================================================
            "Metadata/Items/Hideout/HideoutLightningCoil": " (Dinge fürs Versteck)",
            # =================================================================
            # Piece
            # =================================================================
            "Metadata/Items/UniqueFragments/FragmentUniqueShield1_1": " (1 von 4)",
            "Metadata/Items/UniqueFragments/FragmentUniqueShield1_2": " (2 von 4)",
            "Metadata/Items/UniqueFragments/FragmentUniqueShield1_3": " (3 von 4)",
            "Metadata/Items/UniqueFragments/FragmentUniqueShield1_4": " (4 von 4)",
            "Metadata/Items/UniqueFragments/FragmentUniqueSword1_1": " (1 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueSword1_2": " (2 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueSword1_3": " (3 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueStaff1_1": " (1 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueStaff1_2": " (2 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueStaff1_3": " (3 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueBelt1_1": " (1 von 2)",
            "Metadata/Items/UniqueFragments/FragmentUniqueBelt1_2": " (2 von 2)",
            "Metadata/Items/UniqueFragments/FragmentUniqueQuiver1_1": " (1 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueQuiver1_2": " (2 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueQuiver1_3": " (3 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueHelmet1_1": " (1 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueHelmet1_2": " (2 von 3)",
            "Metadata/Items/UniqueFragments/FragmentUniqueHelmet1_3": " (3 von 3)",
            # =================================================================
            # MTX
            # =================================================================
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x1": " (1x1)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x2": " (1x2)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x3": " (1x3)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox1x4": " (1x4)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x1": " (2x1)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x2": " (2x2)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x3": " (2x3)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox2x4": " (2x4)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox3x2": " (3x2)",
            "Metadata/Items/MicrotransactionCurrency/MysteryBox3x3": " (3x3)",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionIronMaiden": "",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionInfernalAxe": (
                " (Weapon Skin)"
            ),
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionColossusSword": "",
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionLegionBoots": (
                " (Mikrotransaktion)"
            ),
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionLegionGloves": (
                " (Mikrotransaktion)"
            ),
            "Metadata/Items/MicrotransactionItemEffects/MicrotransactionScholarBoots": (
                " (Mikrotransaktion)"
            ),
            "Metadata/Items/Pets/DemonLion": " (Haustier)",
            # =================================================================
            # Quest items
            # =================================================================
            "Metadata/Items/QuestItems/GoldenPages/Page1": " (1 von 4)",
            "Metadata/Items/QuestItems/GoldenPages/Page2": " (2 von 4)",
            "Metadata/Items/QuestItems/GoldenPages/Page3": " (3 von 4)",
            "Metadata/Items/QuestItems/GoldenPages/Page4": " (4 von 4)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier8_1": " (1 von 2)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier8_2": " (2 von 2)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier9_1": " (1 von 3)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier9_2": " (2 von 3)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier9_3": " (3 von 3)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier10_1": " (1 von 3)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier10_2": " (2 von 3)",
            "Metadata/Items/QuestItems/MapUpgrades/MapUpgradeTier10_3": " (3 von 3)",
            # =================================================================
            # =================================================================
            # ==================== Germany only conflicts =====================
            # =================================================================
            # =================================================================
            # Schleifstein
            "Metadata/Items/Currency/CurrencyWeaponQuality": "",
            "Metadata/Items/HideoutInteractables/StrDexCraftingBench": " (Dinge fürs Versteck)",
        },
    }

    # Apped name without changing inventory icon
    _NAME_APPENDIX_BY_ID_2 = {
        "English": {
            # =================================================================
            # Map fragments
            # =================================================================
            "Metadata/Items/MapFragments/CurrencyAfflictionFragment": " (map fragment)",
        },
    }

    _LANG = {
        "English": {
            "Low": "Low Tier",
            "Mid": "Mid Tier",
            "High": "High Tier",
            "Uber": "Max Tier",
            "decoration": "%s (%s %s decoration)",
            "decoration_wounded": "%s (%s %s decoration, Wounded)",
            "of": "%s of %s",
            "descent": "Descent",
        },
        "German": {
            "Low": "Niedrige Stufe",
            "Mid": "Mittlere Stufe",
            "High": "Hohe Stufe",
            "Uber": "Maximale Stufe",
            "decoration": "%s (%s %s Dekoration)",
            "decoration_wounded": "%s (%s %s Dekoration, verletzt)",
            "of": "%s von %s",
            "descent": "Descent",
        },
        "Russian": {
            "Low": "низкий уровень",
            "Mid": "средний уровень",
            "High": "высокий уровень",
            "Uber": "максимальный уровень",
            "decoration": "%s (%s %s предмет убежища)",
            "decoration_wounded": "%s (%s %s предмет убежища, Раненый)",
            "of": "%s из %s",
            "descent": "Спуск",
        },
    }

    _EXCLUDE_CLASSES = {
        "HiddenItem",
        "AtlasUpgradeItem",
        "PantheonSoul",
        "MiscMapItem",
        "UniqueFragment",
        "IncursionItem",
        "DelveSocketableCurrency",
        "DelveStackableSocketableCurrency",
        "Incubator",
        "IncubatorStackable",
        "HeistContract",
        "HeistEquipmentWeapon",
        "HeistEquipmentTool",
        "HeistEquipmentUtility",
        "HeistEquipmentReward",
        "HeistBlueprint",
        "HeistObjective",
        "ArchnemesisMod",
        "SentinelDrone",
        "MemoryLine",
        "SanctumSpecialRelic",
        "GiftBox",
        "ConventionTreasure",
        "SkillGemToken",
        "UncutSkillGem_OLD",
        "UncutSupportGem_OLD",
        "UncutReservationGem_OLD",
        # Not released yet
        "Dagger",
        "Claw",
        "TrapTool",
        "Flail",
        "One Hand Sword",
        "Two Hand Sword",
        "One Hand Axe",
        "Two Hand Axe",
        "DivinationCard",
        # Skills are not supported 100% yet
        "Active Skill Gem",
        "Meta Skill Gem",
        "Support Skill Gem",
    }

    # Unreleased or disabled items to avoid exporting to the wiki
    _SKIP_ITEMS_BY_ID = {
        # =================================================================
        # Skill Gems
        # =================================================================
        "Metadata/Items/Gem/SkillGemAscendancyUnleash",  # because have the same skill_id as staff one
        "Metadata/Items/Gem/SkillGemUnusable",
        "Metadata/Items/Gems/SkillGemSummonBeast",
        "Metadata/Items/Gems/SkillGemSummonSpectre",
        "Metadata/Items/Gems/SkillGemWither",
        "Metadata/Items/Gems/SkillGemCastOnDeath",
        "Metadata/Items/Gems/SkillGemCastOnMeleeKill",
        "Metadata/Items/Gems/SkillGemCastOnMeleeStun",
        "Metadata/Items/Gems/SkillGemCastWhenDamageTaken",
        "Metadata/Items/Gems/SkillGemCastWhenStunned",
        "Metadata/Items/Gems/SkillGemCastWhileChannelling",
        "Metadata/Items/Gems/SkillGemDarkPact",
        "Metadata/Items/Gems/SkillGemDemonMagus",
        "Metadata/Items/Gem/SkillGemDetonateMinion",
        "Metadata/Items/Gem/SkillGemElementalSiphon",
        "Metadata/Items/Gems/SkillGemExsanguinate",
        "Metadata/Items/Gems/SupportGemFerociousRoar",
        "Metadata/Items/Gems/SkillGemFuriousSlam",
        "Metadata/Items/Gem/SkillGemHydra",
        "Metadata/Items/Gems/SkillGemLightningStorm",
        "Metadata/Items/Gems/SkillGemBearMaul",
        "Metadata/Items/Gems/SkillGemBearRampage",
        "Metadata/Items/Gems/SkillGemRollingMagma",
        "Metadata/Items/Gems/SkillGemShroud",
        "Metadata/Items/Gems/SkillGemSoulrend",
        "Metadata/Items/Gems/SkillGemSpinningInferno",
        "Metadata/Items/Gems/SkillGemSummonMercenaryCompanion",
        "Metadata/Items/Gems/SkillGemSummonWolfCompanion",
        "Metadata/Items/Gems/SkillGemTornado",
        "Metadata/Items/Gems/SkillGemVolcano",
        "Metadata/Items/Gem/SkillGemPlaytestAttack",
        "Metadata/Items/Gem/SkillGemPlaytestSpell",
        "Metadata/Items/Gem/SkillGemPlaytestSlam",
        "Metadata/Items/Gem/SkillGemPlayerDefaultSpearOffHand",
        # Item granted versions
        "Metadata/Items/Gems/SkillGemSkeletalWarrior",
        "Metadata/Items/Gems/SkillGemCorpsewadeCorpseCloud",
        "Metadata/Items/Gem/SkillGemUniqueDuskVigilTriggeredBlazingCluster",
        "Metadata/Items/Gem/SkillGemUniqueEarthboundTriggeredSpark",
        "Metadata/Items/Gems/UniqueSkillGemHeraldOfAsh",
        "Metadata/Items/Gems/UniqueSkillGemHeraldOfIce",
        "Metadata/Items/Gems/UniqueSkillGemHeraldOfThunder",
        "Metadata/Items/Gems/UniqueSkillGemWitheringPresence",
        # New 0.3.0
        "Metadata/Items/Gem/SkillGemIceFragments",
        "Metadata/Items/Gems/SkillGemGraveCommand",
        "Metadata/Items/Gems/SkillGemDarkTempest",
        "Metadata/Items/Gems/SkillGemCastCurseOnBlock",
        "Metadata/Items/Gems/SkillGemSoulCrystal",
        # Weapon default attacks
        "Metadata/Items/Gem/SkillGemPlayerDefault1HAxe",
        "Metadata/Items/Gem/SkillGemPlayerDefault2HAxe",
        "Metadata/Items/Gem/SkillGemPlayerDefaultAxeAxe",
        "Metadata/Items/Gem/SkillGemPlayerDefault1HSword",
        "Metadata/Items/Gem/SkillGemPlayerDefault2HSword",
        "Metadata/Items/Gem/SkillGemPlayerDefaultSwordSword",
        "Metadata/Items/Gem/SkillGemPlayerDefaultFlail",
        "Metadata/Items/Gem/SkillGemPlayerDefaultDagger",
        "Metadata/Items/Gem/SkillGemPlayerDefaultDaggerDagger",
        "Metadata/Items/Gem/SkillGemPlayerDefaultClaw",
        "Metadata/Items/Gem/SkillGemPlayerDefaultClawClaw",
        # =================================================================
        # Support Gems
        # =================================================================
        "Metadata/Items/Gems/SupportGemChanceToFreeze",
        "Metadata/Items/Gems/SupportEnervation",
        "Metadata/Items/Gems/SupportGemFusillade",
        "Metadata/Items/Gems/SupportGemFrozenVortex",
        "Metadata/Items/Gems/SupportGemInfusion",
        "Metadata/Items/Gems/SupportGemInvocation",
        "Metadata/Items/Gem/SupportGemNadir",
        "Metadata/Items/Gem/SupportGemSoulbreaker",
        "Metadata/Items/Gems/SupportGemSpreadingFrost",
        "Metadata/Items/Gem/SupportGemUndermine",
        "Metadata/Items/Gem/SupportGemHoarfrost",
        "Metadata/Items/Gems/SupportGemShockSiphon",
        # New 0.3.0
        "Metadata/Items/Gem/SupportGemAdhereThree",
        "Metadata/Items/Gems/SupportGemAftershockThree",
        "Metadata/Items/Gem/SupportGemAncestralCallThree",
        "Metadata/Items/Gems/SupportGemDiscombobulate",  # Daze
        "Metadata/Items/Gem/SupportGemBloodintheEyes",  # Hobble
        "Metadata/Items/Gems/SupportGemOverabundanceThree",
        "Metadata/Items/Gems/SupportGemPersistenceThree",
        "Metadata/Items/Gem/SupportGemGrudge",
        # New 0.3.1
        "Metadata/Items/Gem/SupportGemFlamePillar",
        # =================================================================
        # Uncut Gems
        # =================================================================
        # =================================================================
        # Amulets
        # =================================================================
        "Metadata/Items/Amulets/FourAmuletDelirium1",
        # =================================================================
        # Rings
        # =================================================================
        "Metadata/Items/Rings/RingDemigods1",
        # =================================================================
        # Belts
        # =================================================================
        "Metadata/Items/Belts/BeltDemigods1",
        # =================================================================
        # Charms
        # =================================================================
        "Metadata/Items/Flasks/FourCharm13",
        # =================================================================
        # Body armours
        # =================================================================
        "Metadata/Items/Armours/BodyArmours/BodyDemigods1",
        "Metadata/Items/Armours/BodyArmours/FourBodyDemigod",
        "Metadata/Items/Armours/BodyArmours/FourBodyDexInt8",
        "Metadata/Items/Armours/BodyArmours/FourBodyDexInt9",
        "Metadata/Items/Armours/BodyArmours/FourBodyDexInt10",
        "Metadata/Items/Armours/BodyArmours/FourBodyStrDex10",
        "Metadata/Items/Armours/BodyArmours/FourBodyStrInt10",
        "Metadata/Items/Armours/BodyArmours/FourBodyStr11",
        "Metadata/Items/Armours/BodyArmours/FourBodyInt11",
        "Metadata/Items/Armours/BodyArmours/FourBodyDexInt11",
        "Metadata/Items/Armours/BodyArmours/FourBodyStrInt11",
        "Metadata/Items/Armours/BodyArmours/FourBodyDex12",
        "Metadata/Items/Armours/BodyArmours/FourBodyDexInt12",
        "Metadata/Items/Armours/BodyArmours/FourBodyStrDex12a",
        "Metadata/Items/Armours/BodyArmours/FourBodyStrDex12b",
        "Metadata/Items/Armours/BodyArmours/FourBodyStrDex12c",
        "Metadata/Items/Armours/BodyArmours/FourBodyDex13",
        "Metadata/Items/Armours/BodyArmours/FourBodyStr13",
        "Metadata/Items/Armours/BodyArmours/FourBodyDexInt13",
        "Metadata/Items/Armours/BodyArmours/FourBodyStrDex13",
        "Metadata/Items/Armours/BodyArmours/FourBodyStrInt13",
        "Metadata/Items/Armours/BodyArmours/FourBodyDex14",
        "Metadata/Items/Armours/BodyArmours/FourBodyStr15",
        # =================================================================
        # Helmets
        # =================================================================
        "Metadata/Items/Armours/Helmets/HelmetWreath1",
        "Metadata/Items/Armours/Helmets/HelmetDemigods1",
        "Metadata/Items/Armours/Helmets/FourHelmetDexInt7",
        "Metadata/Items/Armours/Helmets/FourHelmetStrInt7",
        "Metadata/Items/Armours/Helmets/FourHelmetStrDex8",
        "Metadata/Items/Armours/Helmets/FourHelmetStrInt8",
        "Metadata/Items/Armours/Helmets/FourHelmetStr9",
        "Metadata/Items/Armours/Helmets/FourHelmetInt9",
        "Metadata/Items/Armours/Helmets/FourHelmetStr10",
        "Metadata/Items/Armours/Helmets/FourHelmetInt10",
        "Metadata/Items/Armours/Helmets/FourHelmetStr11",
        # =================================================================
        # Gloves
        # =================================================================
        "Metadata/Items/Armours/Gloves/GlovesDemigods1",
        "Metadata/Items/Armours/Gloves/FourGlovesDemigod",
        "Metadata/Items/Armours/Gloves/FourGlovesStrInt5",
        "Metadata/Items/Armours/Gloves/FourGlovesStrInt6",
        "Metadata/Items/Armours/Gloves/FourGlovesDex7",
        "Metadata/Items/Armours/Gloves/FourGlovesDex8",
        "Metadata/Items/Armours/Gloves/FourGlovesStr8",
        "Metadata/Items/Armours/Gloves/FourGlovesInt8",
        # =================================================================
        # Boots
        # =================================================================
        "Metadata/Items/Armours/Boots/BootsDemigods1",
        "Metadata/Items/Armours/Boots/FourBootsDemigod",
        "Metadata/Items/Armours/Boots/FourBootsStrDex5",
        "Metadata/Items/Armours/Boots/FourBootsStrInt5",
        "Metadata/Items/Armours/Boots/FourBootsStrDex6",
        "Metadata/Items/Armours/Boots/FourBootsDexInt6",
        "Metadata/Items/Armours/Boots/FourBootsStrInt6",
        "Metadata/Items/Armours/Boots/FourBootsDex7",
        "Metadata/Items/Armours/Boots/FourBootsStr7",
        "Metadata/Items/Armours/Boots/FourBootsInt7",
        "Metadata/Items/Armours/Boots/FourBootsDex8",
        "Metadata/Items/Armours/Boots/FourBootsStr8",
        "Metadata/Items/Armours/Boots/FourBootsInt8",
        # =================================================================
        # Shields
        # =================================================================
        "Metadata/Items/Armours/Shields/ShieldDemigods",
        "Metadata/Items/Armours/Shields/FourShieldDemigod",
        "Metadata/Items/Armours/Shields/FourShieldStrDex9",
        "Metadata/Items/Armours/Shields/FourShieldStrInt9",
        "Metadata/Items/Armours/Shields/FourShieldStrDex10",
        "Metadata/Items/Armours/Shields/FourShieldStrInt10",
        "Metadata/Items/Armours/Shields/FourShieldStr11",
        "Metadata/Items/Armours/Shields/FourShieldStrDex11",
        "Metadata/Items/Armours/Shields/FourShieldStrInt11",
        "Metadata/Items/Armours/Shields/FourShieldStr12",
        # =================================================================
        # Bucklers
        # =================================================================
        "Metadata/Items/Armours/Shields/FourShieldDex13",
        # =================================================================
        # Foci
        # =================================================================
        "Metadata/Items/Armours/Focii/FourFocus11",
        "Metadata/Items/Armours/Focii/FourFocus12",
        "Metadata/Items/Armours/Focii/FourFocus13",
        # =================================================================
        # Bows
        # =================================================================
        "Metadata/Items/Weapons/TwoHandWeapons/Bows/FourBow9Endgame",
        "Metadata/Items/Weapons/TwoHandWeapons/Bows/FourBow11",
        "Metadata/Items/Weapons/TwoHandWeapons/Bows/FourBow12",
        # =================================================================
        # Crossbows
        # =================================================================
        "Metadata/Items/Weapons/TwoHandWeapons/Crossbows/FourCrossbow11",
        "Metadata/Items/Weapons/TwoHandWeapons/Crossbows/FourCrossbow12",
        "Metadata/Items/Weapons/TwoHandWeapons/Crossbows/FourCrossbow13",
        # =================================================================
        # Quarterstaves
        # =================================================================
        "Metadata/Items/Weapons/TwoHandWeapons/Staves/FourQuarterstaff11",
        "Metadata/Items/Weapons/TwoHandWeapons/Staves/FourQuarterstaff12",
        # =================================================================
        # Staves
        # =================================================================
        "Metadata/Items/Weapons/TwoHandWeapons/Staves/FourStaff4",
        "Metadata/Items/Weapons/TwoHandWeapons/Staves/FourStaff7",
        "Metadata/Items/Weapons/TwoHandWeapons/Staves/FourStaff9",
        "Metadata/Items/Weapons/TwoHandWeapons/Staves/FourStaff13",
        "Metadata/Items/Weapons/TwoHandWeapons/Staves/FourStaff14",
        # =================================================================
        # Wands
        # =================================================================
        "Metadata/Items/Weapons/OneHandWeapons/Wands/FourWand9",
        "Metadata/Items/Weapons/OneHandWeapons/Wands/FourWand10",
        "Metadata/Items/Weapons/OneHandWeapons/Wands/FourWand11",
        "Metadata/Items/Weapons/OneHandWeapons/Wands/FourWand12",
        # =================================================================
        # Sceptres
        # =================================================================
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre3",
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre5",
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre7",
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre8",
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre9",
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre11",
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre12",
        "Metadata/Items/Weapons/OneHandWeapons/Sceptres/FourSceptre13",
        # =================================================================
        # Maces
        # =================================================================
        "Metadata/Items/Weapons/OneHandWeapons/OneHandMaces/FourOneHandMace11",
        "Metadata/Items/Weapons/TwoHandWeapons/TwoHandMaces/FourTwoHandMace11",
        "Metadata/Items/Weapons/TwoHandWeapons/TwoHandMaces/FourTwoHandMace12",
        # =================================================================
        # Fishing rods
        # =================================================================
        "Metadata/Items/Weapons/TwoHandWeapon/FishingRods/FishingRod1",
        # =================================================================
        # Currency items
        # =================================================================
        "Metadata/Items/Currency/CurrencyIdentificationShard",
        "Metadata/Items/Currency/CurrencyPortal",
        "Metadata/Items/Currency/CurrencyPassiveRefund",
        "Metadata/Items/Currency/CurrencyAtlasPassiveRefund",
        "Metadata/Items/Currency/CurrencyConvertToNormal",
        "Metadata/Items/Currency/CurrencyUpgradeToRareShard",
        "Metadata/Items/Currency/CurrencyRerollMagic",
        "Metadata/Items/Currency/CurrencyRerollMagicShard",
        "Metadata/Items/Currency/CurrencyRerollRareShard",
        "Metadata/Items/Currency/CurrencyRerollUnique",
        "Metadata/Items/Currency/CurrencyRerollUniqueShard",
        "Metadata/Items/Currency/CurrencyAddModToRareShard",
        "Metadata/Items/Currency/CurrencyFractureRareShard",
        "Metadata/Items/Currency/CurrencyDuplicateShard",
        "Metadata/Items/Currency/CurrencyRerollSocketColours",
        "Metadata/Items/Currency/CurrencyRerollSocketLinks",
        "Metadata/Items/Currency/CurrencyRerollImplicit",
        "Metadata/Items/Currency/CurrencyRerollDefences",
        "Metadata/Items/Currency/CurrencyStrongboxQuality",
        "Metadata/Items/Currency/CurrencyStrongboxQualityShard",
        "Metadata/Items/Currency/CurrencyStrongboxQualityInfused",
        "Metadata/Items/Currency/CurrencyEnkindlingOrb",
        "Metadata/Items/Currency/CurrencyInstillingOrb",
        "Metadata/Items/Currency/CurrencyRerollSkillQualityType",
        "Metadata/Items/Currency/CurrencyRerollSupportQualityType",
        "Metadata/Items/Currency/CurrencyAddGemExperience",
        "Metadata/Items/Currency/CurrencyRemoveModShard",
        "Metadata/Items/Currency/CurrencyUpgradeMapTier",
        "Metadata/Items/Currency/CurrencyUpgradeMapTierShard",
        "Metadata/Items/Currency/CurrencyRerollMapType",
        "Metadata/Items/Currency/CurrencyRerollMapTypeShard",
        "Metadata/Items/Currency/CurrencyImprint",
        "Metadata/Items/Currency/CurrencyImprintOrb",
        "Metadata/Items/Currency/CurrencyExtractOil",
        "Metadata/Items/Currency/CurrencyItemiseCapturedMonster",
        "Metadata/Items/Currency/CurrencyItemisedCapturedMonster",
        "Metadata/Items/Currency/CurrencyUpgradeToRareAndSetSockets",
        "Metadata/Items/Currency/CurrencyUpgradeToRareAndSetSocketsShard",
        "Metadata/Items/Currency/CurrencyConflictOrb",
        "Metadata/Items/Currency/CurrencyUpgradeInfluenceMod",
        "Metadata/Items/Currency/CurrencySilverCoin",
        "Metadata/Items/Currency/CurrencyRitualSplinter",
        "Metadata/Items/Currency/CurrencyRitualStone",
        "Metadata/Items/MapFragments/CurrencyHarvestBossKey",
        "Metadata/Items/Heist/HeistCoin",
        "Metadata/Items/Currency/CurrencyHeistArmourEnchant",
        "Metadata/Items/Currency/CurrencyHeistWeaponEnchant",
        "Metadata/Items/AtlasExiles/AddModToRareCrusader",
        "Metadata/Items/AtlasExiles/AddModToRareHunter",
        "Metadata/Items/AtlasExiles/AddModToRareRedeemer",
        "Metadata/Items/AtlasExiles/AddModToRareWarlord",
        "Metadata/Items/AtlasExiles/ApplyInfluence",
        "Metadata/Items/Currency/CurrencyMapQuality",
        "Metadata/Items/Currency/CurrencyItemisedProphecy",
        "Metadata/Items/Currency/CurrencyPerandusCoin",
        "Metadata/Items/Currency/CurrencyItemiseSextantModifier",
        "Metadata/Items/Currency/CurrencyRespecShapersOrb",
        "Metadata/Items/Currency/CurrencyToucanFeather",
        "Metadata/Items/Currency/CurrencyKiwiFeather",
        "Metadata/Items/Currency/CurrencyVultureFeather",
        "Metadata/Items/Currency/CurrencyPeacockFeather",
        "Metadata/Items/Currency/CurrencySkillGemToken",
        # =================================================================
        # SoulCores
        # =================================================================
        # Tempered runes
        "Metadata/Items/SoulCores/RunePhysicalLesser",
        "Metadata/Items/SoulCores/RunePhysical",
        "Metadata/Items/SoulCores/RunePhysicalGreater",
        # =================================================================
        # Vault key items
        # =================================================================
        "Metadata/Items/MapFragments/VaultKeySanctumBase",
        "Metadata/Items/MapFragments/ClassicVaultKey",
        "Metadata/Items/MapFragments/UberShaperVaultKey",
        "Metadata/Items/MapFragments/UberUberElderVaultKey",
        "Metadata/Items/MapFragments/UberVenariusVaultKey",
        "Metadata/Items/MapFragments/UberSirusVaultKey",
        "Metadata/Items/MapFragments/UberMavenVaultKey",
        "Metadata/Items/MapFragments/UberSearingExarchVaultKey",
        "Metadata/Items/MapFragments/UberEaterOfWorldsVaultKey",
        "Metadata/Items/MapFragments/VaalVaultKey",
        "Metadata/Items/MapFragments/VoidbornVaultKey",
        "Metadata/Items/MapFragments/TencentVoidbornVaultKey",
        "Metadata/Items/MapFragments/340VaultKey",
        # =================================================================
        # Quest items
        # =================================================================
        # Books merged into 1
        "Metadata/Items/QuestItems/Gallows/Act1/UnaSkillBook",
        "Metadata/Items/QuestItems/Gallows/Act2/SerpentClanCasterBossDrop",
        "Metadata/Items/QuestItems/Gallows/Act2/FinalLetterSkillBook",
        "Metadata/Items/QuestItems/Gallows/Act3/QuadrillaSkillBook",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric3",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric6",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric9",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric12",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric15",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookUniqueMaps2",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookUniqueMaps3",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookUniqueMaps4",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookUniqueMaps5",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookPinnacle2",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookPinnacle3",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookPinnacle4",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBreach2",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBreach3",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBreach4",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookDelirium2",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookDelirium3",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookDelirium4",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookRitual2",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookRitual3",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookRitual4",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookExpedition2",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookExpedition3",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookExpedition4",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBoss2",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBoss3",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBoss4",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBoss5",
        # New in PoE2
        "Metadata/Items/QuestItems/Gallows/Act3/BogWitchSkillBook",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric2",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric4",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric5",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric7",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric8",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric10",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric11",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric13",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookGeneric14",
        "Metadata/Items/QuestItems/Gallows/Act1/FinnsPotion",
        "Metadata/Items/QuestItems/Gallows/Act2/BurningHeart",
        "Metadata/Items/QuestItems/Gallows/Act2/DjinnFlaskEmpty",
        "Metadata/Items/QuestItems/Gallows/Act2/DjinnFlaskFull",
        "Metadata/Items/QuestItems/Gallows/Act2/MaggotHusk",
        # New 0.3.0
        "Metadata/Items/QuestItems/Gallows/Interlude/QimarWaterVial_02",
        "Metadata/Items/QuestItems/Gallows/Interlude/QimarWaterVial_03",
        "Metadata/Items/QuestItems/Gallows/Act4/PrisonerRegeneratingLiver",
        "Metadata/Items/QuestItems/Gallows/Act4/HalfDigestedSulphite",
        "Metadata/Items/QuestItems/Gallows/Act4/ScourgeOfTheSkiesTalons",
        # Old from PoE1
        "Metadata/Items/QuestItems/SkillBooks/DelevelBook",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookElder",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookMaven",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookTangle",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookCleansingFire",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookInfiniteHunger",
        "Metadata/Items/QuestItems/SkillBooks/AtlasSkillBookBlackStar",
        "Metadata/Items/QuestItems/SkillBooks/Descent2_1",
        "Metadata/Items/QuestItems/SkillBooks/Descent2_2",
        "Metadata/Items/QuestItems/SkillBooks/Descent2_3",
        "Metadata/Items/QuestItems/SkillBooks/Descent2_4",
        "Metadata/Items/QuestItems/Act11/MavenMapDeviceAlteration",
        "Metadata/Items/QuestItems/Act11/TangleMapDeviceAlteration",
        "Metadata/Items/QuestItems/Act11/CleansingFireMapDeviceAlteration",
        "Metadata/Items/QuestItems/Sentinel/Controller",
        # =================================================================
        # Instance items
        # =================================================================
        "Metadata/Items/QuestItems/Gallows/Act4/PrisonKey",
        "Metadata/Items/QuestItems/Gallows/Act4/Shovel",
        # =================================================================
        # Misc
        # =================================================================
        # New in PoE2
        "Metadata/Items/Ultimatum/UltimatumKeySpecial",
        "Metadata/Items/Sanctum/SanctumBronzeKeyDrop",
        "Metadata/Items/Sanctum/SanctumSilverKeyDrop",
        "Metadata/Items/Sanctum/SanctumGoldKeyDrop",
        "Metadata/Items/QuestItems/Gallows/Act3/VaalKeyGemMedium2",
        "Metadata/Items/QuestItems/Gallows/Act3/VaalKeyGemMedium3",
        "Metadata/Items/QuestItems/Gallows/Act3/VaalKeyGem2",
        "Metadata/Items/QuestItems/Gallows/Act3/VaalKeyGem3",
        "Metadata/Items/QuestItems/Gallows/Act3/VaalKeyGem4",
        "Metadata/Items/QuestItems/Gallows/Act3/VaalKeyGem5",
        # Old from PoE1
        "Metadata/Items/Heist/HeistEquipmentToolTest",
        "Metadata/Items/Heist/HeistEquipmentWeaponTest",
        "Metadata/Items/Heist/HeistEquipmentUtilityTest",
        "Metadata/Items/Heist/HeistEquipmentRewardTest",
        "Metadata/Items/Weapons/OneHandWeapons/OneHandSwords/StormBladeOneHand",
        "Metadata/Items/Weapons/TwoHandWeapons/TwoHandSwords/StormBladeTwoHand",
        "Metadata/Items/Weapons/OneHandWeapons/Daggers/EtherealBlade1",
        "Metadata/items/Weapons/OneHandWeapons/OneHandSwords/OneHandSwordDemigods1",
        "Metadata/Items/Classic/MysteryLeaguestone",
        "Metadata/Items/MapFragments/CurrencyFragmentPantheonFlask",
        "Metadata/Items/MapFragments/RitualFragment",
        "Metadata/Items/MapFragments/CurrencyMavenKey",
        "Metadata/Items/MapFragments/CurrencyMavenKeyFragment",
        # =================================================================
        # Cosmetic items
        # =================================================================
        "Metadata/Items/MicrotransactionCurrency/MysteryBox1x1",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox1x2",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox1x3",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox1x4",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox2x1",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox2x2",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox2x3",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox2x4",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox3x2",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox3x3",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox3x1",
        "Metadata/Items/MicrotransactionCurrency/MysteryBox4x1",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem1x1",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem1x2",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem1x3",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem1x4",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem2x1",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem2x2",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem2x3",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem2x4",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem3x2",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem3x1",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem4x1",
        "Metadata/Items/MicrotransactionCurrency/GiftBox1x1",
        "Metadata/Items/MicrotransactionCurrency/GiftBox1x2",
        "Metadata/Items/MicrotransactionCurrency/GiftBox1x3",
        "Metadata/Items/MicrotransactionCurrency/GiftBox1x4",
        "Metadata/Items/MicrotransactionCurrency/GiftBox2x1",
        "Metadata/Items/MicrotransactionCurrency/GiftBox2x2",
        "Metadata/Items/MicrotransactionCurrency/GiftBox2x3",
        "Metadata/Items/MicrotransactionCurrency/GiftBox2x4",
        "Metadata/Items/MicrotransactionCurrency/GiftBox3x2",
        "Metadata/Items/MicrotransactionCurrency/GiftBox3x1",
        "Metadata/Items/MicrotransactionCurrency/GiftBox4x1",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem1x1Ritual",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem1x2Ritual",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem1x3Ritual",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem1x4Ritual",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem2x1Ritual",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem2x2Ritual",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem2x3Ritual",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem2x4Ritual",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem3x2Ritual",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem3x1Ritual",
        "Metadata/Items/MicrotransactionCurrency/HiddenItem4x1Ritual",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionRemoveCosmetic",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionSpectralThrowEbony",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionFirstBlood",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionTitanPlate",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionStatueSummonSkeletons2",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionStatueSummonSkeletons3",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionStatueSummonSkeletons4",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionAlternatePortal",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionBloodSlam",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionNewRaiseSpectre",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionNewRaiseZombie",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionNewTotem",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionPlinthWarp",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionWhiteWeapon",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionYellowWeapon",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionHeartWeapon2015",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionPortalSteam1",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionTestCharacterPortrait",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionTestCharacterPortrait2",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionAuraEffect1",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionAuraEffect2",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionAuraEffect3",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionAuraEffect4",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionBloodRavenSummonRagingSpirit",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMarkOfThePhoenixPurple",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionWuqiWeaponEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionBlackguardCape",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDemonhandClaw",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDivineShield",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionEldritchWings",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionCelestialAuraEffect1",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionCelestialAuraEffect2",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionCelestialAuraEffect3",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSoulstealerWings1",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSoulstealerWings2",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSoulstealerWings3",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSoulstealerWings4",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionZenithBackAttachment1",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionZenithBackAttachment2",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionZenithBackAttachment3",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionOrionWings1",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionOrionWings2",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionOrionWings3",
        "Metadata/Items/MicrotransactionCharacterEffects/"
        "MicrotransactionImaginationCharacterEffect1",
        "Metadata/Items/MicrotransactionCharacterEffects/"
        "MicrotransactionImaginationCharacterEffect2",
        "Metadata/Items/MicrotransactionCharacterEffects/"
        "MicrotransactionImaginationCharacterEffect3",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGlimmerwoodWings1",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGlimmerwoodWings2",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGlimmerwoodWings3",
        "Metadata/Items/MicrotransactionCharacterEffects/"
        "MicrotransactionCelestialTentaclesCharacterEffect1",
        "Metadata/Items/MicrotransactionCharacterEffects/"
        "MicrotransactionCelestialTentaclesCharacterEffect2",
        "Metadata/Items/MicrotransactionCharacterEffects/"
        "MicrotransactionCelestialTentaclesCharacterEffect3",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMarkOfTheWarriorWings",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionFireBallFrame",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionLightningBallFrame",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionIceBallFrame",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCrystalHelmet",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCrystalBoots",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCrystalGloves",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCrystalBodyArmour",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCrystalBackAttachment",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMadmanHelmet",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMadmanBoots",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMadmanGloves",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMadmanBodyArmour",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionStalkerWingsUpgrade1",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionStalkerWingsUpgrade2",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionStalkerWingsUpgrade3",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDragonHunterHelmetAttachment",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionBlueDragonPortalEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCrusaderPortalEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionAltDunShield",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionDarkDeicidePortraitFrame",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionKitavaWings",
        "Metadata/Items/MicrotransactionCharacterEffects/"
        "MicrotransactionBenevolenceCharacterEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionEternalSyndicatePortalEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionHighPriestWeapon",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionSurvivorsGoggles",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionChieftainHelmet",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionChieftainBoots",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionChieftainGloves",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionChieftainBodyArmour",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionReaperPortalEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDoomGauntletShield",
        "Metadata/Items/MicrotransactionItemEffects/"
        "MicrotransactionChieftainApparitionPortalEffect",
        "Metadata/Items/MicrotransactionItemEffects/"
        "MicrotransactionInfernalSteamPoweredPortalEffect",
        "Metadata/Items/Pets/Eyeball1",
        "Metadata/Items/Pets/Eyeball2",
        "Metadata/Items/Pets/Eyeball3",
        "Metadata/Items/Pets/Eyeball4",
        "Metadata/Items/Pets/Eyeball5",
        "Metadata/Items/Pets/CaneToad2",
        "Metadata/Items/Pets/CaneToad3",
        "Metadata/Items/Pets/CaneToad4",
        "Metadata/Items/Pets/CaneToad5",
        "Metadata/Items/Pets/CaneToad6",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionStygianInfernalBlowEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionCelestialSweepEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionNightfallDualStrikeEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSunriseNecrolordHelmet",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSunriseNecrolordBoots",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSunriseNecrolordGloves",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSunriseNecrolordBodyArmour",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSunriseNecrolordCloak",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSunriseNecrolordWings",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionMyrmidonHydrosphereEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDragonSwordPortalEffect",
        "Metadata/Items/Pets/AmberCatPet",
        "Metadata/Items/Pets/LargeInfernalBasilisk",
        "Metadata/Items/Pets/Merveil",
        "Metadata/Items/Pets/FootballPet",
        "Metadata/Items/Pets/ElderDarkseerPet",
        "Metadata/Items/Pets/SurvivorsHoundPet",
        "Metadata/Items/Pets/TwilightPegasusPet",
        "Metadata/Items/Pets/BuccaneerPet",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionScourgeFootprintsEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionNullifierHood",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionOblivionBodyArmour1",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionOblivionBodyArmour2",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionOblivionBodyArmour3",
        "Metadata/Items/Pets/GoddessPet",
        "Metadata/Items/Pets/GargoyleAmaranthinePremium",
        "Metadata/Items/Pets/GargoyleAmaranthinePremiumExpired",
        "Metadata/Items/Pets/Hundun",
        "Metadata/Items/Pets/Taowu",
        "Metadata/Items/Pets/Taotie",
        "Metadata/Items/Pets/Qiongqi",
        "Metadata/Items/Pets/DaughterOfSinPet",
        "Metadata/Items/Pets/SpectralGryffonPet",
        "Metadata/Items/Pets/BladeSoulPet",
        "Metadata/Items/Pets/LunarRabbitPet",
        "Metadata/Items/Pets/GhostriderCompanionPet",
        "Metadata/Items/Pets/AlchemistCompanionPet",
        "Metadata/Items/Pets/AlchemistCompanionPetTemporary",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGreenLichHelmet",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGreenLichBodyArmour",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGreenLichGloves",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGreenLichBoots",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGreenLichCloak",
        "Metadata/Items/MicrotransactionCurrency/MicrotransactionSalvageFragmentSmall",
        "Metadata/Items/MicrotransactionCurrency/MicrotransactionSalvageFragment",
        "Metadata/Items/MicrotransactionCurrency/MicrotransactionSalvageFragmentLarge",
        "Metadata/Items/MicrotransactionCurrency/TradeMarketTab",
        "Metadata/Items/MicrotransactionCurrency/TradeMarketBuyoutTab",
        "Metadata/Items/MicrotransactionCurrency/TradeMarketBuyoutTabTemporary",
        "Metadata/Items/MicrotransactionCurrency/MysteryBoxLightChaos",
        "Metadata/Items/MicrotransactionCurrency/MysteryBoxRadiant",
        "Metadata/Items/MicrotransactionCurrency/MysteryBoxGoddess",
        "Metadata/Items/MicrotransactionCurrency/MysteryBoxLunar",
        "Metadata/Items/MicrotransactionCurrency/MysteryBoxBladeSoul",
        "Metadata/Items/MicrotransactionCurrency/ProxyArcticAurora10",
        "Metadata/Items/MicrotransactionCurrency/ProxyFireworksClassic20",
        "Metadata/Items/MicrotransactionCurrency/ProxyFireworksDarkSoulercoaster15",
        "Metadata/Items/MicrotransactionCurrency/ProxySkinTransferPack5",
        "Metadata/Items/MicrotransactionCurrency/ProxySkinTransferPack10",
        "Metadata/Items/MicrotransactionCurrency/ProxySkinTransferPack50",
        "Metadata/Items/MicrotransactionCurrency/TradeMarketBuyoutTabTemporary",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionAltLioneyesGlare",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionAlchemistsBelt",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionAnnihilationSmiteEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSurvivorsGogglesHelmetAttachment",  # noqa
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionReLinkQuary",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCathedralWings1",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCathedralWings2",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCathedralWings3",
        "Metadata/Items/MicrotransactionCurrency/MicrotransactionPetConvertToBlueGhostrider",
        "Metadata/Items/MicrotransactionCurrency/HideoutMonsterStatueCreator",
        "Metadata/Items/Pets/Mimic",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionVoodooAsenathsGentleTouch",
        "Metadata/Items/Pets/HeritageHummingbirdPet",
        "Metadata/Items/Pets/AristocratCatPet",
        "Metadata/Items/Pets/AristocratLargeCatPet",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionAristocratWeaponEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionOceanGreatbow",
        "Metadata/Items/Pets/AyeAyePet",
        "Metadata/Items/Pets/BlackWidowSpider",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionJadeMarohiErqi",
        "Metadata/Items/Pets/FangtoothMorayPet",
        "Metadata/Items/Pets/FaridunLizardPet",
        "Metadata/Items/Pets/FennecFoxPet",
        "Metadata/Items/Pets/FluffyMothPet",
        "Metadata/Items/Pets/LifeBatteryPet",
        "Metadata/Items/Pets/ManaBatteryPet",
        "Metadata/Items/Pets/NecroticCatPet",
        "Metadata/Items/Pets/PetRockVaal",
        "Metadata/Items/Pets/PetRockStatues",
        "Metadata/Items/Pets/WolverinePet",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionPhoenixEggRiseofthePhoenix",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionArachnamagusPortalEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionPhantomPortalEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSmokePortalEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionTentacleApparitionPortalEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionBerserkerHelmet",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCentipedeCorpseCloak",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionCorruptedCharacterEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionCrystalGreatbow",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDarkCollectorsSack",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionDarkRustKingsWeapon",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionDemonicFireballEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionDemonicRainofArrowsEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionDruidicLochtonialCaress",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionElementalStaff",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionElvenKnightBodyArmour",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionElvenKnightBoots",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionElvenKnightGloves",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionElvenKnightHelmet",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionEtherealWeapon",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionReaperWeaponEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionFireflyCursor",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGiftCollectorsSack",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGlacialGreatbow",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGoldRustKingsWeapon",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGoldenGreatbow",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGothicWeapon",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionJunkCollectorsSack",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionKnightmasterHood",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionKnightmasterWeaponEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMasqueradeCloak",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMossyGreatbow",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionNullifierHood",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionOblivionGroundSlamEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionOblivionRainofArrowsEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionOmniscienceScalingBodyArmour",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionOnyxOblivionFireballEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionOnyxOblivionGroundSlamEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionOnyxOblivionRainofArrowsEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionOphidianCovenant",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionOxidizedRustKingsWeapon",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionPhantomAuraEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionPhantomWeaponEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionRustKingsWeapon",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionSawbladeLightningStrikeEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSharkFinBackAttachment",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSiegeGreatbow",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSilverGreatbow",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionTreasureCollectorsSack",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionVineReapEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionVulcanWeaponEffect",
        "Metadata/Items/Pets/GiantHornetPet",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionAlchemistPoisonousConcoctionEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionAuspiciousCycloneEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionAuspiciousFlameDashEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionAuspiciousToxicRainEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionCelestialNovaAuraEffect1",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionCelestialNovaAuraEffect2",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionCelestialNovaAuraEffect3",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionDarkwoodHeraldEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionGhastlyMarinersTotem",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionGoreLacerateEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMoltenEarthshatterEffect",
        "Metadata/Items/MicrotransactionSkillEffects/MicrotransactionStarfallRageVortexEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSunDyadianDawn",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionFireworksSingapore",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionSilkweaversThreadOfHope",
        "Metadata/Items/Pets/ScorpionPurple",
        "Metadata/Items/Pets/FrogPurpleCrown",
        "Metadata/Items/Pets/WhiteTiger",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionBalefireOblivionWings1",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionBalefireOblivionWings2",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionBalefireOblivionWings3",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGemlingSageWings1",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGemlingSageWings2",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionGemlingSageWings3",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMercurialWings",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMistWings",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionWinterDragonWings",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMistBodyArmour",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMistBoots",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionLithomancersCharacterEffect1",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionLithomancersCharacterEffect2",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionLithomancersCharacterEffect3",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionMarakethCharacterEffectUpgrade1",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionMarakethCharacterEffectUpgrade2",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionMarakethCharacterEffectUpgrade3",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionMarakethCharacterEffectUpgrade4",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionMarakethCharacterEffectUpgrade5",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionMarakethCharacterEffectUpgrade6",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionMercurialCharacterEffect1",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionMercurialCharacterEffect2",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionMercurialCharacterEffect3",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionMistCharacterEffect",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionRedLanternCharacterEffect",
        "Metadata/Items/MicrotransactionCharacterEffects/MicrotransactionWinterDragonCharacterEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionMistFootprintsEffect",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionReaperFootprints",
        "Metadata/Items/MicrotransactionItemEffects/MicrotransactionFieryHands",
        # =================================================================
        # Hideout decorations
        # =================================================================
        # Hideout totem test variants, not needed
        "Metadata/Items/Hideout/HideoutTotemPoleTest",
        "Metadata/Items/Hideout/HideoutTotemPole2Test",
        "Metadata/Items/Hideout/HideoutTotemPole3Test",
        "Metadata/Items/Hideout/HideoutTotemPole4Test",
        "Metadata/Items/Hideout/HideoutTotemPole5Test",
        "Metadata/Items/Hideout/HideoutTotemPole6Test",
        "Metadata/Items/Hideout/HideoutTotemPole7Test",
        "Metadata/Items/Hideout/HideoutTotemPole8Test",
        "Metadata/Items/Hideout/HideoutTotemPole9Test",
        "Metadata/Items/Hideout/HideoutTotemPole10Test",
        "Metadata/Items/Hideout/HideoutTotemPole11Test",
        "Metadata/Items/Hideout/HideoutTotemPole12Test",
        "Metadata/Items/Hideout/HideoutTotemPole13Test",
        "Metadata/Items/Hideout/HideoutTotemPole14Test",
        "Metadata/Items/Hideout/HideoutTotemPole15Test",
        "Metadata/Items/Hideout/HideoutTotemPole16Test",
        "Metadata/Items/Hideout/HideoutTotemPole17Test",
        "Metadata/Items/Hideout/HideoutTotemPole18Test",
        "Metadata/Items/Hideout/HideoutTotemPole19Test",
        "Metadata/Items/Hideout/HideoutTotemPole20Test",
        "Metadata/Items/Hideout/HideoutTotemPole21Test",
        "Metadata/Items/Hideout/HideoutTotemPole22Test",
        "Metadata/Items/Hideout/HideoutTotemPole23Test",
        "Metadata/Items/Hideout/HideoutTotemPole24Test",
        "Metadata/Items/Hideout/HideoutTeleport",
        "Metadata/Items/Hideout/HideoutTelepad",
        "Metadata/Items/Hideout/HideoutTeleportProxy",
        "Metadata/Items/Hideout/HideoutTeleportOwnerOnly",
        "Metadata/Items/Hideout/HideoutMiracleMapDevice1",
        "Metadata/Items/Hideout/HideoutMiracleMapDevice2",
        "Metadata/Items/Hideout/HideoutMiracleMapDevice3",
        "Metadata/Items/Hideout/HideoutShengjingBuildingSupplies1",
        "Metadata/Items/Hideout/HideoutShengjingBuildingSupplies2",
        "Metadata/Items/Hideout/HideoutShengjingBuildingSupplies3",
        "Metadata/Items/Hideout/HideoutShengjingBuildingSupplies4",
        "Metadata/Items/Hideout/HideoutShengjingBuildingSupplies5",
        "Metadata/Items/Hideout/HideoutSteampunkWalls",
        "Metadata/Items/Hideout/HideoutSteampunkWaypoint",
        "Metadata/Items/Hideout/HideoutSteampunkVats",
        "Metadata/Items/Hideout/HideoutSteampunkTables",
        "Metadata/Items/Hideout/HideoutSteampunkPipes",
        "Metadata/Items/Hideout/HideoutLionStatueKneeling2",
        "Metadata/Items/MicrotransactionCurrency/MicrotransactionMysteryBoxWrapper",
        # =================================================================
        # Non-stackable resonators from before 3.8.0
        # =================================================================
        "Metadata/Items/Delve/DelveSocketableCurrencyUpgrade1",
        "Metadata/Items/Delve/DelveSocketableCurrencyUpgrade2",
        "Metadata/Items/Delve/DelveSocketableCurrencyUpgrade3",
        "Metadata/Items/Delve/DelveSocketableCurrencyUpgrade4",
        "Metadata/Items/Delve/DelveSocketableCurrencyReroll1",
        "Metadata/Items/Delve/DelveSocketableCurrencyReroll2",
        "Metadata/Items/Delve/DelveSocketableCurrencyReroll3",
        "Metadata/Items/Delve/DelveSocketableCurrencyReroll4",
        # =================================================================
        # Non-stackable incubators from before 3.16.0
        # =================================================================
        "Metadata/Items/Currency/CurrencyIncubationEssence",
        "Metadata/Items/Currency/CurrencyIncubationCurrency",
        "Metadata/Items/Currency/CurrencyIncubationUniques",
        "Metadata/Items/Currency/CurrencyIncubationMaps",
        "Metadata/Items/Currency/CurrencyIncubationUniqueMaps",
        "Metadata/Items/Currency/CurrencyIncubationAbyss",
        "Metadata/Items/Currency/CurrencyIncubationFragments",
        "Metadata/Items/Currency/CurrencyIncubationScarabs",
        "Metadata/Items/Currency/CurrencyIncubationEssenceHigh",
        "Metadata/Items/Currency/CurrencyIncubationFossils",
        "Metadata/Items/Currency/CurrencyIncubationPerandus",
        "Metadata/Items/Currency/CurrencyIncubationDivination",
        "Metadata/Items/Currency/CurrencyIncubationTalismans",
        "Metadata/Items/Currency/CurrencyIncubationLabyrinthHelm",
        "Metadata/Items/Currency/CurrencyIncubationArmour6Linked",
        "Metadata/Items/Currency/CurrencyIncubationCurrencyMid",
        "Metadata/Items/Currency/CurrencyIncubationUniqueLeague",
        "Metadata/Items/Currency/CurrencyIncubationArmourShaperElder",
        "Metadata/Items/Currency/CurrencyIncubationWeaponShaperElder",
        "Metadata/Items/Currency/CurrencyIncubationTrinketShaperElder",
        "Metadata/Items/Currency/CurrencyIncubationMapElder",
        "Metadata/Items/Currency/CurrencyIncubationBreach",
        "Metadata/Items/Currency/CurrencyIncubationHarbingerShard",
        "Metadata/Items/Currency/CurrencyIncubationGem",
        "Metadata/Items/Currency/CurrencyIncubationGeneric",
        "Metadata/Items/Currency/CurrencyIncubationGemLow",
        "Metadata/Items/Currency/CurrencyIncubationBestiary",
        "Metadata/Items/Currency/CurrencyIncubationBlight",
        "Metadata/Items/Currency/CurrencyIncubationMetamorph",
        "Metadata/Items/Currency/CurrencyIncubationDelirium",
        # =================================================================
        # Old map fragments
        # =================================================================
        "Metadata/Items/MapFragments/VaalFragment1_1",
        "Metadata/Items/MapFragments/VaalFragment1_2",
        "Metadata/Items/MapFragments/VaalFragment1_3",
        "Metadata/Items/MapFragments/VaalFragment1_4",
        "Metadata/Items/MapFragments/VaalFragment2_1",
        "Metadata/Items/MapFragments/VaalFragment2_2",
        "Metadata/Items/MapFragments/VaalFragment2_3",
        "Metadata/Items/MapFragments/VaalFragment2_4",
        "Metadata/Items/MapFragments/ProphecyFragment1",
        "Metadata/Items/MapFragments/ProphecyFragment2",
        "Metadata/Items/MapFragments/ProphecyFragment3",
        "Metadata/Items/MapFragments/ProphecyFragment4",
        "Metadata/Items/MapFragments/ShaperFragment1",
        "Metadata/Items/MapFragments/ShaperFragment2",
        "Metadata/Items/MapFragments/ShaperFragment3",
        "Metadata/Items/MapFragments/ShaperFragment4",
        "Metadata/Items/MapFragments/FragmentPantheonFlask",
        "Metadata/Items/MapFragments/BreachFragmentFire",
        "Metadata/Items/MapFragments/BreachFragmentCold",
        "Metadata/Items/MapFragments/BreachFragmentLightning",
        "Metadata/Items/MapFragments/BreachFragmentPhysical",
        "Metadata/Items/MapFragments/BreachFragmentChaos",
        "Metadata/Items/Labyrinth/OfferingToTheGoddess",
        # =================================================================
        # Watchstones
        # =================================================================
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgradeFinal",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_1",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_2",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_3",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_4",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_5",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_6",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_7",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade1_8",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_1",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_2",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_3",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_4",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_5",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_6",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_7",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade2_8",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_1",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_2",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_3",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_4",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_5",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_6",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_7",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade3_8",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_1",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_2",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_3",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_4",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_5",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_6",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_7",
        "Metadata/Items/AtlasUpgrades/AtlasRegionUpgrade4_8",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable1_1",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable1_2",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable1_3",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable1_4",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable1_5",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable1_6",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable1_7",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable1_8",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable2_1",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable2_2",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable2_3",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable2_4",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable2_5",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable2_6",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable2_7",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable2_8",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable3_1",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable3_2",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable3_3",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable3_4",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable3_5",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable3_6",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable3_7",
        "Metadata/Items/AtlasUpgrades/AtlasUpgradeCraftable3_8",
    }

    _ITEM_SKIP_PATTERNS = {
        "Active Skill Gem": {
            r"SkillGemUnknown",
        },
        "Support Skill Gem": {
            r"SupportGemUnknown",
        },
        "UncutSkillGemStackable": {
            r"SkillGemUncut(?!1$)\d+",
        },
        "UncutSupportGemStackable": {
            r"SupportGemUncut(?!1$)\d+",
        },
        "UncutReservationGemStackable": {
            r"ReservationGemUncut(?!4$)\d+",
        },
        "StackableCurrency": {
            r"CurrencyEldritch",
            r"ScoutingReports",
            r"CurrencySealMap",
            r"CurrencyItemisedSextant",
            r"CurrencyHellscape",
            r"HarvestSeed",
            r"CurrencyLegion",
            r"CurrencyIncursionVial",
            r"CurrencyDelveCrafting",
            r"CurrencyBreach[^S]",
            r"CurrencyHarbinger",
            r"SentinelCurrency",
            r"BestiaryNet",
            r"RandomFossilOutcome",
            r"CurrencyIncursionCorrupt",
            r"CurrencyAddAtlasMod",
        },
        "MapFragment": {
            r"Scarabs",
            r"CurrencyOfferingToTheGoddess",
            r"CurrencyLegion",
            r"Maven/MavenMap",
            r"CurrencyVaalFragment",
            r"CurrencyElderFragment",
            r"CurrencyShaperFragment",
            r"CurrencyProphecyFragment",
            r"CurrencyUberElderFragment",
            r"CurrencySirusFragment",
        },
        "MiscMapItem": {
            r"Maven/MavenMap",
        },
        "Breachstone": {
            r"CurrencyBreachFragment.+",
        },
        "QuestItem": {
            r"SkillBooks/Book-a",
            r"Heist/QuestItems",
            r"Heist/QuestContracts",
            r"ShaperMemoryFragments",
            r"MapUpgrades",
            r"Maven/MavenMap",
            r"MapFragments/Primordial/Quest",
        },
        "Microtransaction": {
            r"Garena",
            r"Tencent",
            r"Jingwei",
            r"Chiyou",
            r"Auspicious.*Dragon",
            r"Jinli",
            r"MicrotransactionGoddess",
            r"MicrotransactionLunar",
            r"GodOfThunder",
            r"AltDeicide",
            r"Freya",
            r"Hasina",
            r"Skadi",
            r"Upgrade.*Scroll",
            r"Convert.*Scroll",
            r"Premium.*Pet",
            r"UnifiedAuraEffect",
            r"MicrotransactionWrapper",
            r"MicrotransactionDance",
        },
    }

    _PLACEHOLDER_IMAGES = {"Art/2DItems/Hideout/HideoutPlaceholder.dds"}

    _attribute_map = OrderedDict(
        (
            ("Str", "strength"),
            ("Dex", "dexterity"),
            ("Int", "intelligence"),
        )
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parsed_args = None
        self._language = config.get_option("language")
        if self._language != "English":
            self.rr2 = RelationalReader(
                path_or_file_system=self.file_system,
                files=["BaseItemTypes.dat64"],
                read_options={
                    "use_dat_value": False,
                    "auto_build_index": True,
                },
                raise_error_on_missing_relation=False,
                language="English",
            )
        else:
            self.rr2 = None

    def _skill_gem(self, infobox: OrderedDict, base_item_type):
        try:
            skill_gem = self.rr["SkillGems.dat64"].index["BaseItemType"][base_item_type.rowid]
        except KeyError:
            return False

        result = []
        for gem_type in skill_gem["GemEffects"]:
            copy = infobox.copy()
            if self._skill_gem_type(copy, base_item_type, skill_gem, gem_type):
                result.append(copy)

        return result

    def _skill_gem_type(self, infobox: OrderedDict, base_item_type, skill_gem, gem_type):
        name = gem_type["Name"]
        if "[DNT]" in name or "[DNT-UNUSED]" in name:
            return False
        if skill_gem["IsVaalVariant"]:
            infobox["is_vaal_skill_gem"] = "true"
            if gem_type["ItemColor"] != 3:
                return False
        if skill_gem["VaalVariant_BaseItemType"]:
            infobox["vaal_variant_id"] = skill_gem["VaalVariant_BaseItemType"]["Id"]
        if name:
            infobox["name"] = name
            infobox["base_item_id"] = infobox.pop("metadata_id")

        # SkillGems.dat
        for attr_short, attr_long in self._attribute_map.items():
            if not skill_gem[attr_short]:
                continue
            infobox[attr_long + "_percent"] = skill_gem[attr_short]

        infobox["gem_tags"] = parser.strip_keywords(
            ", ".join([gt["Name"] for gt in gem_type["GemTags"] if gt["Name"]])
        )

        infobox["gem_tier"] = skill_gem["CraftingLevel"]

        ge = gem_type["GrantedEffect"]

        infobox["skill_id"] = ge["Id"]
        additional = gem_type["AdditionalGrantedEffects"]
        if additional:
            infobox["additional_skill_ids"] = ", ".join(a["Id"] for a in additional)

        max_level = 19

        # Active skills descriptions come from ActiveSkill.dat
        if ge["IsSupport"]:
            max_level = 1

            if "SkillGem" not in self.rr["SupportGems.dat64"].index:
                self.rr["SupportGems.dat64"].build_index("SkillGem")

            try:
                supportGem = self.rr["SupportGems.dat64"].index["SkillGem"][skill_gem.rowid]
            except KeyError:
                return False

            infobox["support_gem_category"] = ", ".join(f["Text"] for f in supportGem["Family"])

            if supportGem["FlavourText"]:
                infobox["flavour_text"] = parser.parse_and_handle_description_tags(
                    rr=self.rr,
                    text=supportGem["FlavourText"]["Text"],
                )

            # Only lineage supports have required level
            if supportGem["IsLineage"]:
                infobox["required_level"] = skill_gem["MinLevelReq"]
            else:
                infobox.pop("required_level")
                infobox.pop("drop_level")

            if gem_type["SupportText"]:
                infobox["gem_description"] = parser.process_keywords(gem_type["SupportText"])

        # Skip more complicated skills
        if ge["AdditionalStatSets"] or additional:
            return False

        primary = OrderedDict()
        self._skill(
            gra_eff=ge,
            infobox=primary,
            parsed_args=self._parsed_args,
            msg_name=base_item_type["Name"],
            max_level=max_level,
            skill_gem=skill_gem,
        )

        for k, v in primary.items():
            infobox[k] = v

        return True

    def _type_inherent_skill(self, infobox, base_item_type):
        if "BaseItemType" not in self.rr["ItemInherentSkills.dat64"].index:
            self.rr["ItemInherentSkills.dat64"].build_index("BaseItemType")

        try:
            item = self.rr["ItemInherentSkills.dat64"].index["BaseItemType"][base_item_type.rowid]
        except KeyError:
            # Allow spear for spear throw
            if base_item_type["ItemClass"]["Id"] == "Spear":
                item = {"SkillsGranted": []}  # Fake it
            else:
                return True

        skills = []

        for skill in item["SkillsGranted"]:
            skills.append(skill["GemEffects"][0]["GrantedEffect"]["Id"])

        # Spear throw
        if base_item_type["ItemClass"]["Id"] == "Spear":
            skills.append("SpearThrowPlayer")

        i = 0
        while i < len(skills):
            infobox[f"inherent_skill{i+1}_id"] = skills[i]
            # Level 0 by default
            if skills[i] in {"ShieldBlockPlayer", "ParryPlayer", "SpearThrowPlayer"}:
                infobox[f"inherent_skill{i+1}_min_level"] = 0
                infobox[f"inherent_skill{i+1}_max_level"] = 0
            i = i + 1

        return True

    def _type_level(self, infobox, base_item_type):
        if base_item_type["Id"] in self._REQUIRED_LEVEL_BY_ID:
            infobox["required_level"] = self._REQUIRED_LEVEL_BY_ID[base_item_type["Id"]]
        else:
            infobox["required_level"] = base_item_type["DropLevel"]
        return True

    _type_attribute = _type_factory(
        data_file="AttributeRequirements.dat64",
        data_mapping=(
            (
                "ReqStr",
                {
                    "template": "required_strength",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "ReqDex",
                {
                    "template": "required_dexterity",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "ReqInt",
                {
                    "template": "required_intelligence",
                    "condition": lambda v: v > 0,
                },
            ),
        ),
        row_index=True,
        fail_condition=True,
    )

    _type_armour = _type_factory(
        data_file="ArmourTypes.dat64",
        data_mapping=(
            (
                "Armour",
                {
                    "template": "armour_min",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "Armour",
                {
                    "template": "armour_max",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "Evasion",
                {
                    "template": "evasion_min",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "Evasion",
                {
                    "template": "evasion_max",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "EnergyShield",
                {
                    "template": "energy_shield_min",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "EnergyShield",
                {
                    "template": "energy_shield_max",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "IncreasedMovementSpeed",
                {
                    "template": "movement_speed",
                    "condition": lambda v: v != 0,
                    "format": lambda v: "{0:n}".format(v / 100),
                },
            ),
        ),
        row_index=True,
    )

    _type_shield = _type_factory(
        data_file="ShieldTypes.dat64",
        data_mapping=(
            (
                "Block",
                {
                    "template": "block",
                },
            ),
        ),
        row_index=True,
    )

    def _apply_flask_buffs(self, infobox, base_item_type, flasks):
        for buff in flasks["UtilityBuff"]:
            stats = [s["Id"] for s in buff["BuffDefinition"]["StatsKeys"]] + [
                s["Id"] for s in buff["BuffDefinition"]["GrantedFlags"]
            ]
            values = buff["StatValues"] + [1 for _ in buff["BuffDefinition"]["GrantedFlags"]]
            tr = self.tc["stat_descriptions.txt"].get_translation(
                stats,
                values,
                full_result=True,
                lang=self._language,
            )
            infobox["buff_stat_text"] = parser.process_keywords(
                "<br>".join([parser.make_inter_wiki_links(line) for line in tr.lines])
            )

    _type_flask = _type_factory(
        data_file="Flasks.dat64",
        data_mapping=(
            (
                "LifePerUse",
                {
                    "template": "flask_life",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "ManaPerUse",
                {
                    "template": "flask_mana",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "RecoveryTime",
                {
                    "template": "flask_duration",
                    "condition": lambda v: v > 0,
                    "format": lambda v: "{0:n}".format(v / 10),
                },
            ),
            (
                "BuffDefinition",
                {
                    "template": "buff_id",
                    "condition": lambda v: v is not None,
                    "format": lambda v: v["Id"],
                },
            ),
        ),
        row_index=True,
        function=_apply_flask_buffs,
    )

    _type_flask_charges = _type_factory(
        data_file="ComponentCharges.dat64",
        index_column="BaseItemTypesKey",
        data_mapping=(
            (
                "MaxCharges",
                {
                    "template": "charges_max",
                },
            ),
            (
                "PerCharge",
                {
                    "template": "charges_per_use",
                },
            ),
        ),
        row_index=False,
    )

    _type_weapon = _type_factory(
        data_file="WeaponTypes.dat64",
        data_mapping=(
            (
                "Critical",
                {
                    "template": "critical_strike_chance",
                    "format": lambda v: "{0:n}".format(v / 100),
                },
            ),
            (
                "Speed",
                {
                    "template": "attack_speed",
                    "format": lambda v: "{0:n}".format(round(1000 / v, 2)),
                },
            ),
            (
                "DamageMin",
                {
                    "template": "physical_damage_min",
                },
            ),
            (
                "DamageMax",
                {
                    "template": "physical_damage_max",
                },
            ),
            (
                "RangeMax",
                {
                    "template": "weapon_range",
                    "format": lambda v: "{0:n}".format(v / 10),
                },
            ),
            (
                "ReloadTime",
                {
                    "template": "reload_time",
                    "condition": lambda v: v > 0,
                    "format": lambda v: "{0:n}".format(v / 1000),
                },
            ),
        ),
        row_index=True,
    )

    _type_spirit = _type_factory(
        data_file="ItemSpirit.dat64",
        data_mapping=(
            (
                "SpiritGranted",
                {
                    "template": "spirit",
                    "condition": lambda v: v > 0,
                },
            ),
        ),
        row_index=True,
        fail_condition=True,
    )

    _type_quest_item = _type_factory(
        data_file="QuestItems.dat64",
        data_mapping=(
            (
                "HelpText",
                {
                    "template": "help_text",
                    "condition": lambda v: v is not None,
                    "format": lambda v: parser.process_keywords(v["Text"]),
                },
            ),
            (
                "Description",
                {
                    "template": "description",
                    "condition": lambda v: v is not None,
                    "format": lambda v: parser.process_keywords(v["Text"]),
                },
            ),
        ),
        row_index=True,
    )

    def _currency_extra(self, infobox, base_item_type, currency):
        if infobox.get("description"):
            infobox["description"] = parser.process_keywords(
                parser.parse_and_handle_description_tags(
                    rr=self.rr,
                    text=infobox["description"],
                )
            )
        if infobox.get("help_text"):
            infobox["help_text"] = parser.process_keywords(
                parser.parse_and_handle_description_tags(
                    rr=self.rr,
                    text=infobox["help_text"],
                )
            )

        return True

    _type_currency = _type_factory(
        data_file="CurrencyItems.dat64",
        data_mapping=(
            (
                "StackSize",
                {
                    "template": "stack_size",
                    "condition": None,
                },
            ),
            (
                "Description",
                {
                    "template": "description",
                    "condition": lambda v: v,
                },
            ),
            (
                "Directions",
                {
                    "template": "help_text",
                    "condition": lambda v: v,
                },
            ),
            (
                "CurrencyTab_StackSize",
                {
                    "template": "stack_size_currency_tab",
                    "condition": lambda v: v > 0,
                },
            ),
        ),
        row_index=True,
        function=_currency_extra,
        fail_condition=True,
    )

    _type_tiered_currency = _type_factory(
        data_file="TieredCurrency.dat64",
        data_mapping=(
            (
                "MinimumModLevel",
                {
                    "template": "crafting_mod_level_min",
                    "condition": lambda v: v,
                },
            ),
        ),
        row_index=True,
        fail_condition=True,
        skip_warning=True,
    )

    _COSMETIC_NAME_MAP = {
        "English": {
            "Skin Transfer": {"cosmetic_type": "Consumable"},
            "Vanishing Dye": {"cosmetic_type": "Miscellaneous"},
            "Invisible Buff Effect": {
                "cosmetic_type": "Skill Gem Effect",
                "cosmetic_target": "Buff",
            },
        }
    }

    _COSMETIC_TYPE_MAP = {
        "English": {
            "Blink and Mirror Arrow Skin": {
                "cosmetic_type": "Skill Gem Effect",
                "cosmetic_target": "Blink Arrow,Mirror Arrow",
            },
            "Blink Mirror Arrow Skin": {
                "cosmetic_type": "Skill Gem Effect",
                "cosmetic_target": "Blink Arrow,Mirror Arrow",
            },
            "Orb Void Sphere Skin": {
                "cosmetic_type": "Skill Gem Effect",
                "cosmetic_target": "Void Sphere",
            },
            "Oblivion Fireball Skin": {
                "cosmetic_type": "Skill Gem Effect",
                "cosmetic_target": "Fireball",
            },
            "Arctic Glacial Cascade": {
                "cosmetic_type": "Skill Gem Effect",
                "cosmetic_target": "Glacial Cascade",
            },
            "Summon Raging Spirits Skin": {
                "cosmetic_type": "Skill Gem Effect",
                "cosmetic_target": "Summon Raging Spirit",
            },
            "Artillery Ballis Skin": {
                "cosmetic_type": "Skill Gem Effect",
                "cosmetic_target": "Artillery Ballista",
            },
            "Banner Skin": {"cosmetic_type": "Skill Gem Effect", "cosmetic_target": "Banner"},
            "Offering Skin": {"cosmetic_type": "Skill Gem Effect", "cosmetic_target": "Offering"},
            "Quiver Skin": {"cosmetic_type": "Weapon Skin", "cosmetic_target": "Quiver"},
            "Apparition Effect": {"cosmetic_type": "Apparition"},
            "Amulet Effect": {"cosmetic_type": "Apparition"},
            "Consumable Effect": {"cosmetic_type": "Consumable"},
            "Charge Skin": {"cosmetic_type": "Alternate Charge Skin"},
            "Cursor Skin": {"cosmetic_type": "Cursor"},
            "Footprints Effect": {"cosmetic_type": "Footprints"},
            "Boots Modifier": {"cosmetic_type": "Footprints"},
            "Flask Effect": {"cosmetic_type": "Flask Skin"},
            "Life Flask Skin": {"cosmetic_type": "Flask Skin", "cosmetic_target": "Life Flask"},
            "Mana Flask Skin": {"cosmetic_type": "Flask Skin", "cosmetic_target": "Mana Flask"},
            "Utility Flask Skin": {
                "cosmetic_type": "Flask Skin",
                "cosmetic_target": "Utility Flask",
            },
            "Quicksilver Flask Effect": {
                "cosmetic_type": "Flask Skin",
                "cosmetic_target": "Quicksilver Flask",
            },
            "Weapon Modifier": {"cosmetic_type": "Weapon Added Effect"},
            "Finisher Effect": {"cosmetic_type": "Weapon Added Effect"},
            "Body Armour Skin": {"cosmetic_type": "Armour Skin"},
            "Body Armour Attachment": {"cosmetic_type": "Armour Attachment"},
            "Helmet Skin and Attachment": {"cosmetic_type": "Helmet Skin / Attachment"},
            "Portal Modification": {"cosmetic_type": "Portal"},
            "Portrait Frame Modification": {"cosmetic_type": "Social Frame"},
        }
    }

    _COSMETIC_ITEM_CLASS_MAP = {
        "English": {
            "Body Armour": "Armour Skin",
            "Jewel": "Passive Jewel Skin",
            "Active Skill Gem": "Skill Gem Effect",
            "Support Skill Gem": "Skill Gem Effect",
            "Claw": "Weapon Skin",
            "Dagger": "Weapon Skin",
            "Rune Dagger": "Weapon Skin",
            "Wand": "Weapon Skin",
            "Axe": "Weapon Skin",
            "Mace": "Weapon Skin",
            "Sword": "Weapon Skin",
            "One Hand Sword": "Weapon Skin",
            "Thrusting One Hand Sword": "Weapon Skin",
            "One Hand Axe": "Weapon Skin",
            "One Hand Mace": "Weapon Skin",
            "Sceptre": "Weapon Skin",
            "Bow": "Weapon Skin",
            "Staff": "Weapon Skin",
            "Two Hand Sword": "Weapon Skin",
            "Two Hand Axe": "Weapon Skin",
            "Two Hand Mace": "Weapon Skin",
            "Warstaff": "Weapon Skin",
            "FishingRod": "Weapon Skin",
        }
    }

    def _cosmetics_extra(self, infobox: dict[str, str], *_):
        if "cosmetic_type" not in infobox:
            return

        if infobox["name"] in self._COSMETIC_NAME_MAP[self._language]:
            infobox.update(self._COSMETIC_NAME_MAP[self._language][infobox["name"]])
            return

        cosmetic_type = infobox["cosmetic_type"].replace(" Of ", " of ").replace("  ", " ")

        if cosmetic_type in self._COSMETIC_TYPE_MAP[self._language]:
            infobox.update(self._COSMETIC_TYPE_MAP[self._language][cosmetic_type])
            return

        if "Name" not in self.rr["MicrotransactionCategory.dat64"].index:
            self.rr["MicrotransactionCategory.dat64"].build_index("Name")
        categories = self.rr["MicrotransactionCategory.dat64"].index["Name"]

        if cosmetic_type not in categories:
            for unique in self.rr["UniqueStashLayout.dat64"]:
                unique_name = unique["WordsKey"]["Text"]
                if unique_name in cosmetic_type or unique_name.replace("The ", "") in cosmetic_type:
                    item_class = unique["UniqueStashTypesKey"]["Name"]
                    unique_type = self._COSMETIC_ITEM_CLASS_MAP[self._language].get(
                        item_class,
                        item_class + " Skin",
                    )

                    if unique_type not in categories:
                        console(
                            f'invalid unique type "{unique_type}" for {infobox["name"]}',
                            msg=Msg.warning,
                        )
                    else:
                        infobox["cosmetic_type"] = unique_type
                        infobox["cosmetic_target"] = unique_name
                        return

            target = cosmetic_type.replace(" Skin", "").replace(" Effect", "")
            suffix = cosmetic_type.replace(target, "")
            if "Name" not in self.rr["BaseItemTypes.dat64"].index:
                self.rr["BaseItemTypes.dat64"].build_index("Name")
            item_index = self.rr["BaseItemTypes.dat64"].index["Name"]
            item_type = next(
                (
                    self._COSMETIC_ITEM_CLASS_MAP[self._language].get(
                        i["ItemClass"]["Id"],
                        i["ItemClass"]["ItemClassCategory"]["Text"] + suffix,
                    )
                    for i in (
                        item_index[target]
                        or item_index[target + " Support"]
                        or item_index[target + " Trap"]
                        or item_index["Summon " + target]
                    )
                    if i["ItemClass"] and i["ItemClass"]["Id"] != "Microtransaction"
                ),
                None,
            )
            if item_type:
                if item_type not in categories:
                    console(
                        f'invalid item type "{item_type}" for {infobox["name"]}', msg=Msg.warning
                    )
                else:
                    infobox["cosmetic_type"] = item_type
                    infobox["cosmetic_target"] = target
                    return

            for tag in self.rr["GemTags.dat64"]:
                if tag["Tag"] and tag["Tag"] + " Skin" in cosmetic_type:
                    infobox["cosmetic_type"] = "Skill Gem Effect"
                    infobox["cosmetic_target"] = tag["Tag"]
                    return

            console(
                f'unknown cosmetic category "{infobox["cosmetic_type"]}" for {infobox["name"]}',
                msg=Msg.warning,
            )
            del infobox["cosmetic_type"]

    _type_microtransaction = _type_factory(
        data_file="CurrencyItems.dat64",
        data_mapping=(),
        function=_cosmetics_extra,
    )

    _type_hideout_doodad = _type_factory(
        data_file="HideoutDoodads.dat64",
        data_mapping=(
            (
                "IsNonMasterDoodad",
                {
                    "template": "is_master_doodad",
                    "format": lambda v: not v,
                },
            ),
            (
                "Variation_AOFiles",
                {
                    "template": "variation_count",
                    "format": lambda v: len(v),
                },
            ),
        ),
        row_index=True,
    )

    def _type_map_extra(self, infobox, base_item_type, waystone):
        if "Tier" not in self.rr["MapTiers.dat64"].index:
            self.rr["MapTiers.dat64"].build_index("Tier")

        for map_tier in self.rr["MapTiers.dat64"]:
            if map_tier["Tier"] == waystone["Tier"]:
                infobox["map_area_level"] = map_tier["Level"]
                break

        return True

    _type_map = _type_factory(
        data_file="Maps.dat64",
        data_mapping=(
            (
                "Tier",
                {
                    "template": "map_tier",
                },
            ),
        ),
        function=_type_map_extra,
        row_index=True,
    )

    def _type_essence_extra(self, infobox, base_item_type, essence):
        if "Essence" not in self.rr["EssenceMods.dat64"].index:
            self.rr["EssenceMods.dat64"].build_index("Essence")

        essence_mods = self.rr["EssenceMods.dat64"].index["Essence"][essence]
        if len(essence_mods) == 0:
            return True

        results = []
        for mod in essence_mods:
            target = parser.process_keywords(mod["TargetItemCategory"]["Text"])
            desc = mod["Text"]

            # Extract from Mod or DisplayMod if no explicit text
            if not desc:
                for mod_key in ("Mod", "DisplayMod"):
                    if mod[mod_key]:
                        stats = self._get_stats(mod=mod[mod_key])
                        desc = "<br>".join(stats)
                        break

            results.append((target, parser.process_keywords(desc)))

        # Append results to infobox
        for target, desc in results:
            infobox["description"] += f"<br>{target}: {desc}"

        return True

    _type_essence = _type_factory(
        data_file="Essences.dat64",
        data_mapping=(
            (
                "MonsterMod",
                {
                    "template": "essence_monster_modifier_ids",
                    "format": lambda v: v["Id"],
                },
            ),
        ),
        row_index=True,
        function=_type_essence_extra,
        fail_condition=True,
        skip_warning=True,
    )

    # TODO:Remove: When liquid emotions mods will be supported on wiki and mods will be exported
    # TODO: 4.0 remove this and EnchantedMod??
    def _type_liquid_emotion_extra(self, infobox, base_item_type, emotions):
        stats = self._get_stats(
            mod=emotions["EnchantedMod"], translation_file="atlas_stat_descriptions.txt"
        )
        desc = parser.process_keywords("<br>".join(stats))
        infobox["implicit1_text"] = "{{c|enchanted|" + desc + "}}"

        return True

    _type_liquid_emotion = _type_factory(
        data_file="BlightCraftingItems.dat64",
        data_mapping=(
            (
                "Tier",
                {
                    "template": "liquid_emotion_tier",
                },
            ),
            (
                "EnchantedMod",
                {
                    "template": "liquid_emotion_mod",
                    "condition": lambda v: v,
                    "format": lambda v: v["Id"],
                },
            ),
        ),
        row_index=True,
        function=_type_liquid_emotion_extra,
        fail_condition=True,
        skip_warning=True,
    )

    _type_abyss_bones = _type_factory(
        data_file="AbyssBenchTicketTypes.dat64",
        data_mapping=(
            (
                "MinimumModLevel",
                {
                    "template": "crafting_mod_level_min",
                    "condition": lambda v: v,
                },
            ),
            (
                "MaximumItemLevel",
                {
                    "template": "crafting_item_level_max",
                    "condition": lambda v: v,
                },
            ),
        ),
        row_index=True,
        fail_condition=True,
        skip_warning=True,
    )

    def _type_soulcore_extra(self, infobox, base_item_type, soulcores):
        # Some have extra desc that is not in game
        if infobox.get("description"):
            infobox.pop("description")

        sc_stat_map = [
            # stats/values key, target text key
            (
                "MartialWeapon",
                "SoulCoreCategoryWeapons",
            ),
            (
                "Armour",
                "SoulCoreCategoryArmour",
            ),
            (
                "CasterWeapon",
                "SoulCoreCategoryCasterWeapons",
            ),
            (
                "AllEquipment",
                "SoulCoreCategoryAllEquipment",
            ),
        ]

        results = []
        for stat_key, target in sc_stat_map:
            if soulcores["Stats" + stat_key]:
                stats = [s["Id"] for s in soulcores[f"Stats{stat_key}"]]
                values = soulcores[f"StatsValues{stat_key}"]
                stats = self._get_stats(
                    stats=stats, values=values, translation_file="stat_descriptions.txt"
                )

                desc = "<br>".join(stats)
                target = self.rr["ClientStrings.dat64"].index["Id"][target]["Text"]

                results.append((parser.process_keywords(target), parser.process_keywords(desc)))

        # Per class SoulCores
        if "BaseItemType" not in self.rr["SoulCoresPerClass.dat64"].index:
            self.rr["SoulCoresPerClass.dat64"].build_index("BaseItemType")

        soulcore_pc = self.rr["SoulCoresPerClass.dat64"].index["BaseItemType"][base_item_type]

        for sc in soulcore_pc:
            stats = [s["Id"] for s in sc["Stats"]]
            values = sc["StatsValues"]
            stats = self._get_stats(
                stats=stats, values=values, translation_file="stat_descriptions.txt"
            )

            desc = "<br>".join(stats)
            target = sc["ItemClass"]["Name"]

            results.append((target, parser.process_keywords(desc)))

        # Append results to infobox
        infobox["description"] = "<br>".join(f"{target}: {desc}" for target, desc in results)

        return True

    _type_soulcore = _type_factory(
        data_file="SoulCores.dat64",
        data_mapping=(
            (
                "RequiredLevel",
                {
                    "template": "required_level",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "Limit",
                {
                    "template": "augment_limit",
                    "condition": lambda v: v is not None,
                    "format": lambda v: v["Text"].format(v["Limit"]) if v["Text"] else v["Limit"],
                },
            ),
        ),
        row_index=True,
        function=_type_soulcore_extra,
        fail_condition=True,
        skip_warning=True,
    )

    def _type_uncutgem(self, infobox, base_item_type):
        class_id = base_item_type["ItemClass"]["Id"]
        if class_id == "UncutSkillGemStackable":
            if "Quest" in base_item_type["Id"]:
                desc_text = "SkillGemBlueTextNoLevel"
            else:
                desc_text = "SkillGemBlueText"
            help_text = "ItemDescriptionUncutSkillGem"
        elif class_id == "UncutSupportGemStackable":
            desc_text = "SupportGemBlueTextNoLevel"
            help_text = "ItemDescriptionUncutSupportGem"
        elif class_id == "UncutReservationGemStackable":
            desc_text = "PersistentBuffSkillGemBlueText"
            help_text = "ItemDescriptionUncutBuffGem"

        infobox["help_text"] = self.rr["ClientStrings.dat64"].index["Id"][help_text]["Text"]
        infobox["description"] = (
            self.rr["ClientStrings.dat64"].index["Id"][desc_text]["Text"].replace("{0}", "#")
        )

        return True

    """
    This defines the expected data elements for an item class.
    """
    _cls_map = {
        # Jewellery
        "Amulet": (_type_inherent_skill, _type_level),
        "Ring": (_type_inherent_skill, _type_level),
        "Belt": (_type_inherent_skill, _type_level),
        # Armour types
        "Gloves": (_type_inherent_skill, _type_level, _type_attribute, _type_armour),
        "Boots": (_type_inherent_skill, _type_level, _type_attribute, _type_armour),
        "Body Armour": (_type_inherent_skill, _type_level, _type_attribute, _type_armour),
        "Helmet": (_type_inherent_skill, _type_level, _type_attribute, _type_armour),
        "Shield": (_type_inherent_skill, _type_level, _type_attribute, _type_armour, _type_shield),
        "Buckler": (_type_inherent_skill, _type_level, _type_attribute, _type_armour, _type_shield),
        "Focus": (_type_inherent_skill, _type_level, _type_attribute, _type_armour),
        # Martial weapons
        "Claw": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Dagger": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "One Hand Sword": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "One Hand Axe": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "One Hand Mace": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Bow": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Two Hand Sword": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Two Hand Axe": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Two Hand Mace": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Talisman": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "FishingRod": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Warstaff": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Spear": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Crossbow": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Flail": (_type_inherent_skill, _type_level, _type_attribute, _type_weapon),
        "Quiver": (_type_inherent_skill, _type_level),
        # Caster weapons
        "Sceptre": (_type_inherent_skill, _type_level, _type_spirit),
        "Wand": (_type_inherent_skill, _type_level),
        "Staff": (_type_inherent_skill, _type_level),
        "TrapTool": (_type_inherent_skill, _type_level),
        # Flasks
        "LifeFlask": (_type_level, _type_flask, _type_flask_charges),
        "ManaFlask": (_type_level, _type_flask, _type_flask_charges),
        "UtilityFlask": (_type_level, _type_flask, _type_flask_charges),  # Aka charm
        # Gems
        "Active Skill Gem": (_skill_gem,),
        "Support Skill Gem": (
            _type_level,
            _skill_gem,
        ),  # _type_level to make it in one place for all items (lineage)
        "Meta Skill Gem": (_skill_gem,),
        # Uncut gems
        "UncutSkillGemStackable": (_type_uncutgem,),
        "UncutSupportGemStackable": (_type_uncutgem,),
        "UncutReservationGemStackable": (_type_uncutgem,),
        # Currency-like items
        "Currency": (_type_currency),
        "StackableCurrency": (
            _type_currency,
            _type_tiered_currency,
            _type_essence,
            _type_liquid_emotion,
            _type_abyss_bones,
        ),
        "SoulCore": (
            _type_currency,
            _type_soulcore,
        ),
        "Omen": (_type_currency,),
        "HideoutDoodad": (_type_currency, _type_hideout_doodad),
        "Microtransaction": (_type_currency, _type_microtransaction),
        "DivinationCard": (_type_currency,),
        # Misc
        "Map": (_type_map,),  # Aka waystone
        "MapFragment": (_type_currency,),
        "TowerAugmentation": (),  # Aka tablets
        "Breachstone": (_type_currency,),
        "ExpeditionLogbook": (),
        "PinnacleKey": (),
        "QuestItem": (_type_quest_item,),
        "UltimatumKey": (),
        # Sanctum
        "ItemisedSanctum": (),  # Aka trial coins
        "Relic": (),
        # Other
        "InstanceLocalItem": (_type_currency,),
    }

    _conflict_active_skill_gems_map = {
        "Metadata/Items/Gems/SkillGemArcticArmour": True,
        "Metadata/Items/Gems/SkillGemPhaseRun": True,
        "Metadata/Items/Gems/SkillGemLightningTendrils": True,
    }

    def _conflict_active_skill_gems(self, infobox, base_item_type, rr, language):
        appendix = self._conflict_active_skill_gems_map.get(base_item_type["Id"])
        if appendix is None:
            return
        else:
            return base_item_type["Name"]

    def _conflict_quest_items(self, infobox, base_item_type, rr, language):
        qid = base_item_type["Id"].replace("Metadata/Items/QuestItems/Gallows/", "")

        # Map fragments from Act 4
        if qid.startswith("Act4/MapFragment"):
            qid = qid[-1]
            return "%s (%s)" % (
                base_item_type["Name"],
                self._LANG[language]["of"] % (qid, 4),
            )

        return

    def _conflict_hideout_doodad(self, infobox, base_item_type, rr, language):
        try:
            ho = rr["HideoutDoodads.dat64"].index["BaseItemTypesKey"][base_item_type.rowid]
        except KeyError:
            return

        # This is not perfect, but works currently.
        if ho["HideoutNPCsKey"]:
            if base_item_type["Id"].startswith("Metadata/Items/Hideout/HideoutWounded"):
                name_fmt = self._LANG[self._language]["decoration_wounded"]
            else:
                name_fmt = self._LANG[self._language]["decoration"]
            name = name_fmt % (
                base_item_type["Name"],
                ho["HideoutNPCsKey"]["Hideout_NPCsKey"]["ShortName"],
                ho["MasterLevel"],
            )
            infobox["inventory_icon"] = name
            return name
        elif base_item_type["Id"].startswith("Metadata/Items/Hideout/HideoutTotemPole"):
            # Ingore the test doodads on purpose
            if base_item_type["Id"].endswith("Test"):
                return

            return base_item_type["Name"]

    def _conflict_map_fragments(self, infobox, base_item_type, rr, language):
        return base_item_type["Name"]

    def _conflict_divination_card(self, infobox, base_item_type, rr, language):
        return base_item_type["Name"]

    def _conflict_misc_map_item(self, infobox, base_item_type, rr, language):
        return base_item_type["Name"]

    _conflict_resolver_map = {
        "Active Skill Gem": _conflict_active_skill_gems,
        "QuestItem": _conflict_quest_items,
        # TODO: Make a new doodad resolver that doesn't rely on 'HideoutNPCsKey'
        # 'HideoutDoodad': _conflict_hideout_doodad,
        "MapFragment": _conflict_map_fragments,
        "DivinationCard": _conflict_divination_card,
        "MiscMapItem": _conflict_misc_map_item,
    }

    def _parse_class_filter(self, parsed_args):
        if parsed_args.item_class_id:
            return [
                self.rr["ItemClasses.dat64"].index["Id"][cls]["Name"]
                for cls in parsed_args.item_class_id
            ]
        elif parsed_args.item_class:
            self.rr["ItemClasses.dat64"].build_index("Name")
            return [
                self.rr["ItemClasses.dat64"].index["Name"][cls][0]["Name"]
                for cls in parsed_args.item_class
            ]
        else:
            return []

    _skipped_items = set()

    def _maybe_skip(self, base_item_type):
        if base_item_type["Id"] in self._SKIP_ITEMS_BY_ID:
            self._skipped_items.add(base_item_type["Id"])
            return True
        if base_item_type["ItemClass"]["Id"] in self._ITEM_SKIP_PATTERNS:
            for pattern in self._ITEM_SKIP_PATTERNS[base_item_type["ItemClass"]["Id"]]:
                if re.search(pattern, base_item_type["Id"], flags=re.IGNORECASE):
                    self._skipped_items.add(base_item_type["Id"])
                    return True
        return False

    def _process_purchase_costs(self, source, infobox):
        for rarity in constants.RARITY:
            if rarity.id >= 5:
                break
            # for i, (item, cost) in enumerate(
            #         source[rarity.name_lower.title() + 'Purchase'],
            #         start=1):
            #     prefix = 'purchase_cost_%s%s' % (rarity.name_lower, i)
            #     infobox[prefix + '_name'] = item['Name']
            #     infobox[prefix + '_amount'] = cost

    def by_rowid(self, parsed_args):
        return self._export(
            parsed_args,
            self.rr["BaseItemTypes.dat64"][parsed_args.start : parsed_args.end],
        )

    def by_id(self, parsed_args):
        return self._export(
            parsed_args, self._item_column_index_filter(column_id="Id", arg_list=parsed_args.id)
        )

    def by_name(self, parsed_args):
        return self._export(
            parsed_args, self._item_column_index_filter(column_id="Name", arg_list=parsed_args.name)
        )

    def by_filter(self, parsed_args):
        if parsed_args.re_name:
            parsed_args.re_name = re.compile(parsed_args.re_name, flags=re.UNICODE)
        if parsed_args.re_id:
            parsed_args.re_id = re.compile(parsed_args.re_id, flags=re.UNICODE)

        items = []

        for item in self.rr["BaseItemTypes.dat64"]:
            if parsed_args.re_name and not parsed_args.re_name.match(item["Name"]):
                continue

            if parsed_args.re_id and not parsed_args.re_id.match(item["Id"]):
                continue

            items.append(item)

        return self._export(parsed_args, items)

    def _process_base_item_type(self, base_item_type, infobox):
        m_id = base_item_type["Id"]

        infobox["rarity_id"] = "normal"

        # BaseItemTypes.dat
        infobox["name"] = base_item_type["Name"]
        infobox["class_id"] = base_item_type["ItemClass"]["Id"]
        infobox["size_x"] = base_item_type["Width"]
        infobox["size_y"] = base_item_type["Height"]
        if base_item_type["FlavourText"]:
            infobox["flavour_text"] = parser.parse_and_handle_description_tags(
                rr=self.rr,
                text=base_item_type["FlavourText"]["Text"],
            )

        if base_item_type["ItemClass"]["Id"] not in self._IGNORE_DROP_LEVEL_CLASSES:
            if base_item_type["Id"] in self._DROP_LEVEL_BY_ID:
                infobox["drop_level"] = self._DROP_LEVEL_BY_ID[base_item_type["Id"]]
            else:
                infobox["drop_level"] = base_item_type["DropLevel"]

        base_ot = ITFile(parent_or_file_system=self.file_system)
        base_ot.read(self.file_system.get_file(base_item_type["InheritsFrom"] + ".it"))
        try:
            ot = self.it[m_id + ".it"]
        except FileNotFoundError:
            # If we couldn't find an ot for the specific item, use the base ot.
            ot = base_ot
        else:
            # If we did find an ot for the specific item, use it and add things from the base to it.
            ot.merge(base_ot)

        if "enable_rarity" in ot["Mods"]:
            infobox["drop_rarities_ids"] = ", ".join(ot["Mods"]["enable_rarity"])

        tags = [t["Id"] for t in base_item_type["TagsKeys"]]
        infobox["tags"] = ", ".join(tags + list(ot["Base"]["tag"]))

        infobox["metadata_id"] = m_id

        description = ot["Stack"].get("function_text")
        if description:
            infobox["description"] = parser.process_keywords(
                self.rr["ClientStrings.dat64"].index["Id"][description]["Text"]
            )

        help_text = ot["Base"].get("description_text")
        if help_text:
            infobox["help_text"] = infobox["help_text"] = parser.process_keywords(
                "<br>".join(
                    self.rr["ClientStrings.dat64"].index["Id"][help_text]["Text"].splitlines()
                )
            )

        # Prepend charm slots implicit for belts
        if base_item_type["ItemClass"]["Id"] == "Belt":
            if "Id" not in self.rr["Mods.dat64"].index:
                self.rr["Mods.dat64"].build_index("Id")
            base_item_type["Implicit_Mods"].insert(
                0, self.rr["Mods.dat64"].index["Id"]["BeltImplicitCharmSlots3"]
            )

        for i, mod in enumerate(base_item_type["Implicit_Mods"]):
            infobox["implicit%s" % (i + 1)] = mod["Id"]

    def _process_name_conflicts(self, infobox, base_item_type, language):
        rr = self.rr2 if language != self._language else self.rr
        # Get the base item of other language
        base_item_type = rr["BaseItemTypes.dat64"][base_item_type.rowid]

        name = infobox.get("name", base_item_type["Name"])
        cls_id = base_item_type["ItemClass"]["Id"]
        m_id = base_item_type["Id"]
        override = self._NAME_OVERRIDE_BY_ID[language].get(m_id)
        override_2 = self._NAME_OVERRIDE_BY_ID_2[language].get(m_id)
        appendix = self._NAME_APPENDIX_BY_ID[language].get(m_id)
        appendix_2 = self._NAME_APPENDIX_BY_ID_2[language].get(m_id)

        if override is not None:
            name = override
            infobox["inventory_icon"] = name
        if override_2 is not None:
            name = override_2
            infobox["name"] = name
        if appendix is not None:
            name += appendix
            if appendix != "":
                infobox["inventory_icon"] = name
        elif appendix_2 is not None:
            name += appendix_2
        else:
            items = [
                item
                for item in rr["BaseItemTypes.dat64"].index["Name"][name]
                if item["Id"] not in self._skipped_items
            ]
            if len(items) > 1:
                resolver = self._conflict_resolver_map.get(cls_id)
                if resolver:
                    name = resolver(self, infobox, base_item_type, rr, language)
                    if name is None:
                        console(
                            'Unresolved ambiguous item "%s" with name "%s". Skipping'
                            % (m_id, infobox["name"]),
                            msg=Msg.warning,
                        )
                        return
                else:
                    console(
                        'Unresolved ambiguous item "%s" with name "%s". Skipping'
                        % (m_id, infobox["name"]),
                        msg=Msg.warning,
                    )
                    console(
                        'No name conflict handler defined for item class id "%s"' % cls_id,
                        msg=Msg.warning,
                    )
                    return

        if m_id in self._FORCE_INVENTORY_ICON_BY_ID:
            infobox["inventory_icon"] = self._FORCE_INVENTORY_ICON_BY_ID.get(m_id)

        return name

    def _export(self, parsed_args, items):
        classes = self._parse_class_filter(parsed_args)
        if classes:
            items = [item for item in items if item["ItemClass"]["Name"] in classes]
        else:
            items = [item for item in items if item["ItemClass"]["Id"] not in self._EXCLUDE_CLASSES]

        self._parsed_args = parsed_args
        console("Found %s items. Removing disabled items..." % len(items))
        items = [base_item_type for base_item_type in items if not self._maybe_skip(base_item_type)]
        console("%s items left for processing." % len(items))

        console("Loading additional files - this may take a while...")
        self._image_init(parsed_args)

        r = ExporterResult()
        self.rr["BaseItemTypes.dat64"].build_index("Name")

        for item in self.rr["BaseItemTypes.dat64"]:
            if item["ItemClass"]["Id"] in self._EXCLUDE_CLASSES:
                self._skipped_items.add(item["Id"])

        if self._language != "English" and parsed_args.english_file_link:
            self.rr2["BaseItemTypes.dat64"].build_index("Name")

        console("Processing item information...")
        self.num_processed = 0

        for base_item_type in items:
            if "[DNT]" in base_item_type["Name"] or "[DNT-UNUSED]" in base_item_type["Name"]:
                continue

            name = base_item_type["Name"]
            cls_id = base_item_type["ItemClass"]["Id"]
            m_id = base_item_type["Id"]

            self._print_item_rowid(len(items), base_item_type)

            infobox = OrderedDict()
            self._process_base_item_type(base_item_type, infobox)
            self._process_purchase_costs(base_item_type, infobox)

            funcs = self._cls_map.get(cls_id)
            infoboxes = [infobox]
            if funcs:
                for f in funcs:
                    next_infoboxes = []
                    for item in infoboxes:
                        result = f(self, item, base_item_type)
                        if result is False:
                            console(
                                f'Required extra info for item "{name}" with class id '
                                f'"{cls_id}" not found. Skipping.',
                                msg=Msg.warning,
                            )
                            break
                        elif result is True:
                            # normal function - modified the infobox dict
                            next_infoboxes.append(item)
                        else:
                            next_infoboxes.extend(result)
                    infoboxes = next_infoboxes

            for infobox in infoboxes:
                # handle items with duplicate name entries
                page = self._process_name_conflicts(infobox, base_item_type, self._language)
                if page is None:
                    continue
                if self._language != "English" and parsed_args.english_file_link:
                    icon = self._process_name_conflicts(infobox, base_item_type, "English")
                    if cls_id == "DivinationCard":
                        key = "card_art"
                    else:
                        key = "inventory_icon"

                    if icon:
                        infobox[key] = icon
                    else:
                        infobox[key] = self.rr2["BaseItemTypes.dat64"][base_item_type.rowid]["Name"]

                # putting this last since it's usually manually added
                if m_id in self._DROP_DISABLED_ITEMS_BY_ID:
                    infobox["drop_enabled"] = False

                inventory_icon = infobox.get("inventory_icon") or page
                if ":" in inventory_icon:
                    infobox["inventory_icon"] = inventory_icon.replace(":", "")

                cond = ItemWikiCondition(
                    data=infobox,
                    cmdargs=parsed_args,
                )

                wiki_page = [
                    {
                        "page": page,
                        "condition": cond,
                    }
                ]

                if infobox.get("cosmetic_type", None) == "Armour Skin" and "Armour" not in page:
                    wiki_page.append(
                        {
                            "page": page + " Armour",
                            "condition": cond,
                        }
                    )

                ddsfile = base_item_type["ItemVisualIdentityKey"]["DDSFile"]
                if ddsfile and ddsfile in self._PLACEHOLDER_IMAGES:
                    warnings.warn(
                        'Item "%s" has placeholder icon art. Skipping.' % base_item_type["Name"]
                    )
                    continue

                r.add_result(
                    text=cond,
                    out_file="item_%s.txt" % page,
                    wiki_page=wiki_page,
                    wiki_message="Item exporter",
                )

                if parsed_args.store_images:
                    if not ddsfile:
                        warnings.warn(
                            'Missing 2d art inventory icon for item "%s"' % base_item_type["Name"]
                        )
                        continue

                    self._write_dds(
                        data=self.file_system.get_file(ddsfile),
                        out_path=os.path.join(
                            self._img_path,
                            (infobox.get("inventory_icon") or page) + " inventory icon.dds",
                        ),
                        parsed_args=parsed_args,
                        process=self._get_icon_process(infobox, base_item_type),
                    )

                infobox.pop("gem_shader", None)

        return r

    def _resize_icon(self, img: Image):
        max_dimension = max(img.size)
        if max_dimension > self._ICON_MAX_DIMENSION:
            scale = self._ICON_MAX_DIMENSION / max_dimension
            return img.resize(
                (int(img.size[0] * scale), int(img.size[1] * scale)), Image.Resampling.LANCZOS
            )
        return img

    def _get_icon_process(self, infobox: dict[str, str], base_item_type):
        comp = base_item_type["ItemVisualIdentityKey"]["Composition"]
        if comp == 1:  # Flask

            def flask_icon_process(img: Image):
                layer1 = img.crop((105, 0, 210, 212))
                layer2 = img.crop((210, 0, 315, 212))
                layer3 = img.crop((0, 0, 105, 212))
                ico = Image.alpha_composite(layer1, Image.alpha_composite(layer2, layer3))
                ico = self._resize_icon(ico)
                return ico

            return flask_icon_process
        if comp == 3:  # Gem
            return self._get_gem_icon_process(infobox)
        return self._resize_icon

    def _get_gem_icon_process(self, infobox: dict[str, str]):
        if "gem_shader" not in infobox:
            return None

        attrs = {
            k.lower(): int(infobox.get(f"{v}_percent", 0)) for k, v in self._attribute_map.items()
        }
        attr = max(attrs, key=attrs.get)
        var = infobox.pop("gem_shader")

        def process(img: Image):
            adorn = img.crop((0, 0, 78, 78))
            base = img.crop((2 * 78, 0, 3 * 78, 78))
            if var == 3:
                return Image.alpha_composite(base, adorn)
            const = SHADE_LUT[(attr, var)]

            base_rgba = _srgb_to_linear(np.float32(np.asarray(base)) / 255.0)

            # Shade algorithm:
            # * compute luminance influence
            #   float Luminance(float3 color)
            #   {
            #   	return dot(float3(0.299, 0.587, 0.114), color);
            #   }
            # 	const float luminance_influence = pow(Luminance(original_rgb), 0.02);
            base_rgb = base_rgba[:, :, :3]
            base_a = base_rgba[:, :, 3]
            lum_f = (
                base_rgba[:, :, 0] * 0.2999
                + base_rgba[:, :, 1] * 0.587
                + base_rgba[:, :, 2] * 0.114
            )
            lum_f = np.expand_dims(lum_f, axis=2)
            luminance_influence = lum_f**0.02

            # * convert to HSV
            # Not using the same algorithm, leveraging matplotlib
            hsv = matplotlib.colors.rgb_to_hsv(base_rgb)

            # * shift HSV by XYZ, clamp H
            # 	max(modf( hsv_sample.x + effect_params.x, ignore ), 0.024),
            # 	saturate( hsv_sample.y + effect_params.y ),
            # 	saturate( hsv_sample.z + effect_params.z )
            h2 = np.maximum(np.modf(hsv[:, :, 0] + const.hue_factor)[0], 0.024)
            s2 = np.clip(hsv[:, :, 1] + const.sat_factor, 0.0, 1.0)
            v2 = np.clip(hsv[:, :, 2] + const.val_factor, 0.0, 1.0)

            # * convert to "modified" RGB
            # Not using the same HSV algorithm, leveraging matplotlib
            modified_rgb = matplotlib.colors.hsv_to_rgb(np.stack([h2, s2, v2], axis=2))

            # * mix original RGB and modified RGB by luminance influence weighted by W
            # 	const float3 final_rgb = lerp(
            # 		modified_rgb,
            # 		original_rgb,
            # 		lerp(luminance_influence, 0.f, effect_params.w)
            # 	);
            def lerp(a, b, f):
                return a * (1.0 - f) + b * f

            final_mix_f = lerp(luminance_influence, 0.0, const.lum_factor)
            final_rgb = lerp(modified_rgb, base_rgb, final_mix_f)

            shifted_rgba = np.dstack((final_rgb, base_a))
            shifted_base = Image.fromarray(np.uint8(_linear_to_srgb(shifted_rgba) * 255.0), "RGBA")

            # * desaturate, but the parameter for that seems to be 1 so won't bother
            # 	return Desaturate(float4(final_rgb, 1.f) * original_a, saturation) * input.colour;

            ico = Image.alpha_composite(shifted_base, adorn)
            ico = self._resize_icon(ico)
            return ico

        return process

    def _print_item_rowid(self, export_row_count, base_item_type):
        # If we're printing less than 100 rows, print every rowid
        if export_row_count <= 100:
            print_granularity = 1
        else:
            print_granularity = 500

        if (self.num_processed == 0) or self.num_processed % print_granularity == 0:
            console(f"Processing item with rowid {base_item_type.rowid}: {base_item_type['Name']}")
        self.num_processed = self.num_processed + 1
        return

    def _shade_sigil(self, tex, color):
        color = np.reshape(np.array(color + (255,)), (1, 1, 4)) / 255.0
        samples = np.asarray(tex, np.float32) / 255.0
        tex_colour = np.dstack((_srgb_to_linear(samples[:, :, :3]), samples[:, :, 3]))
        final = color * tex_colour
        final[:, :, :3] = _linear_to_srgb(final[:, :, :3])
        return Image.fromarray(np.uint8(final * 255.0), "RGBA")
