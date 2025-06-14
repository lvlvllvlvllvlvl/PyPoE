"""
Utility functions for exporters

Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/util.py                                       |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
===============================================================================

Utility functions for exporters.

Agreement
===============================================================================

See PyPoE/LICENSE
"""

# Python
import re
import socket

from PyPoE.cli.exporter import config

# self
from PyPoE.poe.path import PoEPath

# =============================================================================
# Imports
# =============================================================================


# =============================================================================
# Globals
# =============================================================================

__all__ = [
    "get_content_path",
    "fix_path",
]


# =============================================================================
# Functions
# =============================================================================


def get_content_path(sequel=1):
    """
    Returns the path to the current content.ggpk based on the specified
    config variables for the version & distributor.

    :return: Path of the content ggpk
    :rtype: str

    :raises SetupError: if no valid path was found.
    """
    path = config.get_option("ggpk_path")
    if path == "":
        args = config.get_option("version"), config.get_option("distributor")
        paths = PoEPath(*args).get_installation_paths()
        if paths:
            return next(iter(paths))

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(
            ("patch.pathofexile.com", 12995) if sequel == 1 else ("patch.pathofexile2.com", 13060)
        )
        s.sendall(bytes([1, 7]))
        response = s.recv(1000)
        length = response[34]
        return response[35 : 35 + length * 2].decode("utf-16le")

    else:
        return path


def fix_path(path: str) -> str:
    path = path.replace('"', "'", 2).replace("\t", "")
    if re.search("[a-zA-Z]:.*", path) is not None:
        return path[:2] + re.sub(r":", "_", path[2:])
    else:
        return path
