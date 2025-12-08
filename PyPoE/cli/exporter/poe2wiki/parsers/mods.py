"""
Wiki mods exporter

Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/poe2wiki/parsers/mods.py                      |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
===============================================================================

https://poe2wiki.net

Agreement
===============================================================================

See PyPoE/LICENSE

TODO
===============================================================================

FIX the jewel generator (corrupted)
"""

# =============================================================================
# Imports
# =============================================================================

# Python
from collections import OrderedDict
from functools import partialmethod

# Self
from PyPoE.cli.core import Msg, console
from PyPoE.cli.exporter.poe2wiki import parser
from PyPoE.cli.exporter.poe2wiki.handler import ExporterHandler, ExporterResult
from PyPoE.poe import poe2constants as constants
from PyPoE.poe import text
from PyPoE.poe.file.dat import DatRecord

# =============================================================================
# Globals
# =============================================================================

__all__ = ["ModParser", "ModsHandler"]

# =============================================================================
# Classes
# =============================================================================


class OutOfBoundsWarning(UserWarning):
    pass


class WikiCondition(parser.WikiCondition):
    COPY_KEYS = ("tier_text",)
    COPY_CONDITIONS = {
        "tags": parser.WikiCondition.tagsets_equal,
    }

    NAME = "Mod"


class ModsHandler(ExporterHandler):
    def __init__(self, sub_parser):
        self.parser = sub_parser.add_parser(
            "mods",
            help="Mods Exporter",
        )
        self.parser.set_defaults(func=lambda args: self.parser.print_help())
        lua_sub = self.parser.add_subparsers()

        # Mods
        mparser = lua_sub.add_parser("mods", help="Extract all mods.")
        mparser.set_defaults(func=lambda args: mparser.print_help())

        sub = mparser.add_subparsers(help="Method of extracting mods")

        self.add_default_subparser_filters(sub, cls=ModParser)

        # mods filter
        parser = sub.add_parser("filter", help="Filter mods")
        parser.add_argument(
            "--domain",
            dest="domain",
            help="Mod domain",
            choices=[k.name for k in constants.MOD_DOMAIN],
        )

        parser.add_argument(
            "--generation-type",
            "--type",
            dest="generation_type",
            help="Mod domain",
            choices=[k.name for k in constants.MOD_GENERATION_TYPE],
        )

        self.add_default_parsers(
            parser=parser,
            cls=ModParser,
            func=ModParser.filter,
        )

    def add_default_parsers(self, *args, **kwargs):
        super().add_default_parsers(*args, **kwargs)
        parser = kwargs["parser"]
        self.add_format_argument(parser)


class ModParser(parser.BaseParser):
    # Load files in advance
    _files = [
        "Mods.datc64",
        "Stats.datc64",
        "GoldModPrices.datc64",
    ]

    # Load translations in advance
    _translations = [
        "map_stat_descriptions.txt",
    ]

    _mod_column_index_filter = partialmethod(
        parser.BaseParser._column_index_filter,
        dat_file_name="Mods.dat64",
        error_msg="Several modifiers have not been found:\n%s",
    )

    _COPY_KEYS = OrderedDict(
        (
            (
                "Id",
                {
                    "template": "id",
                },
            ),
            (
                "Families",
                {
                    "template": "mod_groups",
                    "condition": lambda v: v,
                    "format": lambda v: ", ".join([m["Id"] for m in v]),
                },
            ),
            (
                "ModType",
                {
                    "template": "mod_type",
                    "condition": lambda v: v is not None,
                    "format": lambda v: v["Name"],
                },
            ),
            (
                "Domain",
                {
                    "template": "domain",
                },
            ),
            (
                "GenerationType",
                {
                    "template": "generation_type",
                },
            ),
            (
                "Level",
                {
                    "template": "required_level",
                    "condition": lambda v: v > 0,
                },
            ),
        )
    )

    def _append_effect(self, result, mylist, heading):
        mylist.append(heading)

        for line in result.lines:
            mylist.append("* %s" % line)
        for i, stat_id in enumerate(result.missing_ids):
            value = result.missing_values[i]
            if hasattr(value, "__iter__"):
                value = "(%s to %s)" % tuple(value)
            mylist.append("* %s %s" % (stat_id, value))

    def by_rowid(self, parsed_args):
        return self._export(
            parsed_args,
            self.rr["Mods.dat64"][parsed_args.start : parsed_args.end],
        )

    def by_id(self, parsed_args):
        return self._export(
            parsed_args, self._mod_column_index_filter(column_id="Id", arg_list=parsed_args.id)
        )

    def by_name(self, parsed_args):
        return self._export(
            parsed_args, self._mod_column_index_filter(column_id="Name", arg_list=parsed_args.name)
        )

    def filter(self, args):
        mods = []

        filters = []
        if args.domain:
            filters.append(
                {
                    "column": "Domain",
                    "comp": getattr(constants.MOD_DOMAIN, args.domain),
                }
            )

        if args.generation_type:
            filters.append(
                {
                    "column": "GenerationType",
                    "comp": getattr(constants.MOD_GENERATION_TYPE, args.generation_type),
                }
            )

        for mod in self.rr["Mods.dat64"]:
            for filter in filters:
                if mod[filter["column"]] != filter["comp"]:
                    break
            else:
                mods.append(mod)

        return self._export(args, mods)

    def _export(self, parsed_args, mods):
        r = ExporterResult()

        if mods:
            console("Found %s mods. Processing..." % len(mods))
        else:
            console("No mods found for the specified parameters. Quitting.", msg=Msg.warning)
            return r

        # Needed for spawn tags
        self.rr["GoldModPrices.dat64"].build_index("Mod")

        for mod in mods:
            infobox = OrderedDict()

            # Copy over simple fields from the .dat64
            apply_column_map(infobox, self._COPY_KEYS, mod)

            mod_prices = self.rr["GoldModPrices.dat64"].index["Mod"][mod]

            # Tags
            implicit_tags = ", ".join([t["Id"] for t in mod["ImplicitTags"]])
            tags = ", ".join([t["Id"] for t in mod["Tags"]])
            if implicit_tags or tags:
                infobox["tags"] = ", ".join(s for s in [implicit_tags, tags] if s)

            if mod_prices and mod_prices[0]["Tags"]:
                infobox["spawn_tags"] = ", ".join(
                    tag["Id"]
                    for tag, spawn_weight in zip(
                        mod_prices[0]["Tags"], mod_prices[0]["SpawnWeight"]
                    )
                    if spawn_weight
                )

            # Name
            if mod["Name"]:
                root = text.parse_description_tags(mod["Name"])

                def handler(hstr, parameter):
                    return hstr if parameter == "MS" else ""

                infobox["name"] = root.handle_tags({"if": handler, "elif": handler})

            # TODO:Sell price
            # mod value + (base value + inherent skill value) * multipliers,
            # and then sell price back to the vendor is 11% of that
            # mod_prices...

            # TODO: need to look into this before completely removing it.
            if mod["BuffTemplate"] and mod["BuffTemplate"]["BuffDefinitionsKey"]:
                infobox["granted_buff_id"] = mod["BuffTemplate"]["BuffDefinitionsKey"]["Id"]
                infobox["granted_buff_value"] = mod["BuffTemplate"]["AuraRadius"]
            # todo ID for GEPL

            if mod["GrantedEffectsPerLevel"]:
                infobox["granted_skill"] = ", ".join(
                    [k["GrantedEffect"]["Id"] for k in mod["GrantedEffectsPerLevel"]]
                )

            stats = []
            values = []
            buffstats = mod["BuffTemplate"]["StatsKey"] if mod["BuffTemplate"] else []
            for i in constants.MOD_STATS_RANGE:
                k = mod["StatsKey%s" % i]
                if k is None or k in buffstats:
                    continue

                stat = k["Id"]
                value = mod["Stat%sMin" % i], mod["Stat%sMax" % i]

                if value[0] == 0 and value[1] == 0:
                    continue

                stats.append(stat)
                values.append(value)

            infobox["stat_text"] = parser.process_keywords(
                "<br>".join(self._get_stats(stats, values, mod))
            )
            # if mod["BuffTemplate"] and mod["BuffTemplate"]["AuraRadius"]:
            #    radius = mod["BuffTemplate"]["AuraRadius"] / 10
            #    infobox["stat_text"] = re.sub(
            #        r"\[\[Nearby\|?([^]]*)]]",
            #        lambda match: f"{{{{Radius|{match.group(1)}|{radius}m}}}}",
            #        infobox["stat_text"],
            #   )

            for i, (sid, (vmin, vmax)) in enumerate(zip(stats, values), start=1):
                infobox["stat%s_id" % i] = sid
                infobox["stat%s_min" % i] = vmin
                infobox["stat%s_max" % i] = vmax

            cond = WikiCondition(
                data=infobox,
                cmdargs=parsed_args,
            )

            r.add_result(
                text=cond,
                out_file="mod_%s.txt" % infobox["id"],
                wiki_page=[
                    {
                        "page": "Modifier:" + self._format_wiki_title(mod["Id"]),
                        "condition": cond,
                    },
                ],
                wiki_message="Mod updater",
            )

        return r


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
