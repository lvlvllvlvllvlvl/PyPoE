"""
Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/poe2wiki/parsers/passives.py                  |
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

Internal API
-------------------------------------------------------------------------------
"""

# =============================================================================
# Imports
# =============================================================================

import os.path

# Python
import posixpath
import re
import warnings
from collections import OrderedDict
from functools import partialmethod

# self
from PyPoE.cli.core import Msg, console
from PyPoE.cli.exporter.poe2wiki import parser
from PyPoE.cli.exporter.poe2wiki.handler import ExporterHandler, ExporterResult
from PyPoE.poe.file.dat import DatRecord
from PyPoE.poe.file.psg2 import PSGFile

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
        "icon",
    )

    NAME = "Passive skill"
    ADD_INCLUDE = False
    INDENT = 36


def normalize(id):
    return id


class PassiveSkillCommandHandler(ExporterHandler):
    def __init__(self, sub_parser):
        self.parser = sub_parser.add_parser(
            "passive",
            help="Passive skill exporter",
        )
        self.parser.set_defaults(func=lambda args: self.parser.print_help())

        self.add_default_subparser_filters(
            sub_parser=self.parser.add_subparsers(),
            cls=PassiveSkillParser,
        )

        # filtering
        """a_filter = sub.add_parser(
            'filter',
            help='Extract passives using filters.'
        )
        self.add_default_parsers(
            parser=a_filter,
            cls=PassiveSkillParser,
            func=PassiveSkillParser.by_filter,
        )

        a_filter.add_argument(
            '-ft-id', '--filter-id', '--filter-metadata-id',
            help='Regular expression on the id',
            type=str,
            dest='re_id',
        )"""

    def add_default_parsers(self, *args, **kwargs):
        super().add_default_parsers(*args, **kwargs)
        self.add_format_argument(kwargs["parser"])
        self.add_image_arguments(kwargs["parser"])
        kwargs["parser"].add_argument(
            "-ft-id",
            "--filter-id",
            "--filter-metadata-id",
            help="Regular expression on the id",
            type=str,
            dest="re_id",
        )


class PassiveSkillParser(parser.BaseParser):
    _files = [
        "PassiveSkills.datc64",
    ]

    _passive_column_index_filter = partialmethod(
        parser.BaseParser._column_index_filter,
        dat_file_name="PassiveSkills.dat64",
        error_msg="Several passives have not been found:\n%s",
    )

    _MAX_STAT_ID = 5

    _COPY_KEYS = OrderedDict(
        (
            (
                "Id",
                {
                    "template": "id",
                },
            ),
            (
                "PassiveSkillGraphId",
                {
                    "template": "int_id",
                    "format": normalize,
                },
            ),
            (
                "Name",
                {
                    "template": "name",
                    "condition": lambda v: v,
                },
            ),
            (  # icon param added here but handled elsewhere
                "Icon_DDSFile",
                {
                    "template": "icon",
                    # "condition": lambda v: v,
                },
            ),
            (
                "FlavourText",
                {
                    "template": "flavour_text",
                    "condition": lambda v: v,
                    "format": lambda v: v.replace("\n", "<br>").replace("\r", ""),
                },
            ),
            (
                "ReminderStrings",
                {
                    "template": "reminder_text",
                    "condition": lambda v: v,
                    "format": lambda v: "<br>".join([x["Text"] for x in v]),
                },
            ),
            # Atlas related
            (
                "AtlasSubTree",
                {
                    "template": "atlas_sub_tree",
                    "condition": lambda v: v is not None,
                    "format": lambda v: v["Id"],
                },
            ),
            (
                "IsRootOfAtlasTree",
                {
                    "template": "is_atlas_sub_tree_starting_node",
                    "default": False,
                },
            ),
            # Ascendancy related
            (
                "Ascendancy",
                {
                    "template": "ascendancy_class",
                    "condition": lambda v: v is not None,
                    "format": lambda v: v["Name"],
                },
            ),
            (
                "IsAscendancyStartingNode",
                {
                    "template": "is_ascendancy_starting_node",
                    "default": False,
                },
            ),
            # Stat related
            (
                "PassiveSkillBuffs",
                {
                    "template": "buff_id",
                    "condition": lambda v: v,
                    "format": lambda v: ",".join([x["BuffDefinitionsKey"]["Id"] for x in v]),
                },
            ),
            (
                "SkillPointsGranted",
                {
                    "template": "skill_points",
                    "condition": lambda v: v > 0,
                },
            ),
            (
                "GrantedSkill",
                {
                    "template": "granted_skill",
                    "condition": lambda v: v is not None,
                    "format": lambda v: v["GemEffects"][0]["GrantedEffect"]["Id"],
                },
            ),
            # Booleans
            (
                "IsKeystone",
                {
                    "template": "is_keystone",
                    "default": False,
                },
            ),
            (
                "IsNotable",
                {
                    "template": "is_notable",
                    "default": False,
                },
            ),
            (
                "IsAttribute",
                {
                    "template": "is_attribute",
                    "default": False,
                },
            ),
            (
                "IsMultipleChoice",
                {
                    "template": "is_multiple_choice",
                    "default": False,
                },
            ),
            (
                "IsMultipleChoiceOption",
                {
                    "template": "is_multiple_choice_option",
                    "default": False,
                },
            ),
            (
                "IsJustIcon",
                {
                    "template": "is_icon_only",
                    "default": False,
                },
            ),
            (
                "IsJewelSocket",
                {
                    "template": "is_jewel_socket",
                    "default": False,
                },
            ),
            (
                "IsFree",
                {
                    "template": "is_free",
                    "default": False,
                },
            ),
        )
    )

    def _apply_filter(self, parsed_args, passives):
        if parsed_args.re_id:
            parsed_args.re_id = re.compile(parsed_args.re_id, flags=re.UNICODE)
        else:
            return passives

        new = []

        for passive in passives:
            if parsed_args.re_id and not parsed_args.re_id.match(passive["Id"]):
                continue

            new.append(passive)

        return new

    def by_rowid(self, parsed_args):
        return self.export(
            parsed_args,
            self.rr["PassiveSkills.dat64"][parsed_args.start : parsed_args.end],
        )

    def by_id(self, parsed_args):
        return self.export(
            parsed_args, self._passive_column_index_filter(column_id="Id", arg_list=parsed_args.id)
        )

    def by_name(self, parsed_args):
        return self.export(
            parsed_args,
            self._passive_column_index_filter(column_id="Name", arg_list=parsed_args.name),
        )

    def export(self, parsed_args, passives):
        r = ExporterResult()

        passives = self._apply_filter(parsed_args, passives)

        console(f"Found {len(passives)} passives.")

        if not passives:
            console(
                "No passives found for the specified parameters. Quitting.",
                msg=Msg.warning,
            )
            return r

        console("Accessing additional data...")

        psg = PSGFile()
        psg.read(
            file_path_or_raw=self.file_system.get_file("Metadata/PassiveSkillGraph.psg"),
        )

        node_index = {}
        for group in psg.groups:
            for node in group.nodes:
                node_index[normalize(node.passive_skill)] = node
        # Connections are one-way, make them two way
        for psg_id, node in node_index.items():
            for other_psg in node.connections:
                if other_psg in node_index:
                    if psg_id not in node_index[other_psg].connections:
                        node_index[normalize(other_psg)].connections.append(psg_id)
                else:
                    console(f"Missing connection {other_psg} for {psg_id}")

        self.rr["PassiveSkills.dat64"].build_index("PassiveSkillGraphId")

        self._image_init(parsed_args)

        # console("Found %s, parsing..." % len(passives))

        for rowid, passive in enumerate(passives, start=1):
            if "[DNT" in passive["Name"]:
                continue

            infobox = OrderedDict()
            # Print out the row number every 100 rows, and every 1/100th of completion,
            # with a minimum increment of 1
            print_increment = max(len(passives) // 100, 1)
            if (rowid % 100 == 0) or (rowid % print_increment == 0):
                console(f"Processing passive {passive['Id']} at {rowid}")

            # Copy over simple fields from the .dat64
            apply_column_map(infobox, self._COPY_KEYS, passive)

            # Handle icon paths
            self.handle_icon(infobox, passive)

            # Handle stats
            j = 0
            stat_text, j = self.get_stat_text(infobox, j, passive)
            # For now this is being added to the stat text
            buff_stat_text, j = self.get_buff_stat_text(infobox, j, passive)

            if stat_text and buff_stat_text:
                infobox["stat_text"] = stat_text + "<br>" + buff_stat_text
            elif stat_text:
                infobox["stat_text"] = stat_text
            elif buff_stat_text:
                infobox["stat_text"] = buff_stat_text
            else:
                infobox["stat_text"] = ""

            # Handle connections
            node = node_index.get(normalize(passive["PassiveSkillGraphId"]))
            if node and node.connections:
                infobox["connections"] = ", ".join(
                    [
                        self.rr["PassiveSkills.dat64"].index["PassiveSkillGraphId"][
                            normalize(psg_id)
                        ]["Id"]
                        for psg_id in node.connections
                    ]
                )

            cond = WikiCondition(
                data=infobox,
                cmdargs=parsed_args,
            )

            r.add_result(
                text=cond,
                out_file="passive_skill_%s.txt" % infobox["id"],
                wiki_page=[
                    {
                        "page": "Passive Skill:" + self._format_wiki_title(infobox["id"]),
                        "condition": cond,
                    },
                ],
                wiki_message="Passive skill updater",
            )

        return r

    # =============================================================================
    # Functions
    # =============================================================================

    def get_stat_text(self, infobox, j, passive: DatRecord):
        """
        Handle regular stats, adds stat ids and values to infobox
        """
        stat_ids = []
        values = []

        for i in range(0, self._MAX_STAT_ID):
            try:
                stat = passive["Stats"][i]
            except IndexError:
                break
            j = i + 1
            stat_ids.append(stat["Id"])
            infobox["stat%s_id" % j] = stat["Id"]
            values.append(passive["Stat%sValue" % j])
            infobox["stat%s_value" % j] = passive["Stat%sValue" % j]

        stat_text = parser.process_keywords(
            "<br>".join(
                self._get_stats(
                    stats=stat_ids,
                    values=values,
                    translation_file=get_translation_file(bool(passive["AtlasSubTree"])),
                )
            )
        )

        return stat_text, j

    def get_buff_stat_text(self, infobox, j, passive: DatRecord):
        """
        Handle buff stats, adds stat ids and values to infobox
        For now this is being added to the stat text
        """
        stat_text = None
        for ps_buff in passive["PassiveSkillBuffs"]:
            buff_defs = ps_buff["BuffDefinition"]
            # if buff_defs["Binary_StatsKeys"]:
            #    stat_ids = [stat["Id"] for stat in buff_defs["Binary_StatsKeys"]]
            #    values = [1 for _ in stat_ids]
            # else:
            stat_ids = [stat["Id"] for stat in buff_defs["Stats"]]
            values = ps_buff["Buff_StatValues"]

            for i, (sid, val) in enumerate(zip(stat_ids, values)):
                j += 1
                infobox["stat%s_id" % j] = sid
                infobox["stat%s_value" % j] = val

            buff_stat_text = parser.process_keywords(
                "<br>".join(
                    self._get_stats(
                        stats=stat_ids,
                        values=values,
                        translation_file="passive_skill_aura_stat_descriptions.txt",
                    )
                )
            )

            if ps_buff["AuraRadius"]:
                radius = ps_buff["AuraRadius"] / 10
                buff_stat_text = re.sub(
                    r"\[\[Nearby\|?([^]]*)]]",
                    lambda match: f"{{{{Radius|{match.group(1)}|{radius}m}}}}",
                    buff_stat_text,
                )

            if stat_text:
                stat_text += "<br>" + buff_stat_text
            else:
                stat_text = buff_stat_text

        return stat_text, j

    def handle_icon(self, infobox, passive):
        if passive["Icon_DDSFile"]:
            file_path = passive["Icon_DDSFile"]
            file_path_4k = posixpath.join(
                posixpath.dirname(file_path), "4k", posixpath.basename(file_path)
            )
            try:
                data = self.file_system.get_file(file_path_4k)
            except FileNotFoundError:
                data = self.file_system.get_file(file_path)

            infobox["icon"] = posixpath.basename(passive["Icon_DDSFile"]).replace(".dds", "")

            # Extract icons if specified
            if self.parsed_args.store_images:
                if bool(passive["AtlasSubTree"]):
                    icon = "%s atlas" % infobox["icon"]
                elif bool(passive["Ascendancy"]):
                    icon = "%s %s" % (infobox["icon"], passive["Ascendancy"]["Id"])
                else:
                    icon = infobox["icon"]
                self._write_dds(
                    data=data,
                    out_path=os.path.join(self._img_path, "%s passive skill icon.dds" % icon),
                    parsed_args=self.parsed_args,
                )
        # atlas_start_node doesn't have an icon path
        else:
            warnings.warn(f"Icon path file not found for {passive['Id']}: {passive['Name']}")


# =============================================================================
# Functions
# =============================================================================


def apply_column_map(
    infobox, column_map: tuple[tuple[str, dict], ...], list_object: DatRecord | list[DatRecord]
):
    """
    Copy over simple fields from the .dat64

    Parameters
    ----------
    infobox: Dictionary in which values should be added
    column_map: Map to apply
    list_object: File to search for keys
    """
    if not isinstance(list_object, DatRecord):
        list_object = list_object[0]

    for k, data in column_map.items():
        value = list_object[k]

        if data.get("condition") and not data["condition"](value):
            continue

        # Skip default values to reduce size of template
        if value == data.get("default"):
            continue

        if data.get("format"):
            value = data["format"](value)

        infobox[data["template"]] = value


def get_translation_file(is_atlas_passive: bool):
    """
    Determines which translation file should be used
    based on whether the passive skill has an "AtlasSubTree" key

    Parameters
    ----------
    is_atlas_passive: the boolean based on "AtlasSubTree" key
    """
    if is_atlas_passive:
        return "atlas_stat_descriptions.txt"
    else:
        return "passive_skill_stat_descriptions.txt"
