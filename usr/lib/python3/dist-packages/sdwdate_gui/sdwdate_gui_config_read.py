#!/usr/bin/python3 -su

## Copyright (C) 2025 - 2025 ENCRYPTED SUPPORT LLC <adrelanos@whonix.org>
## See the file COPYING for copying conditions.

"""
Allows reading sdwdate-gui config values from Bash scripts.
"""

import sys
from typing import NoReturn

from .sdwdate_gui_shared import (
    ConfigData,
    parse_config_files,
)


def main() -> NoReturn:
    """
    Main function.
    """

    if len(sys.argv) != 2:
        sys.exit(2)

    if not sys.argv[1] in ConfigData.conf_schema:
        print(
            f"ERROR: Unrecognized configuration option '{sys.argv[1]}'!",
            file=sys.stderr,
        )
        sys.exit(1)
    parse_config_files()
    print(ConfigData.conf_dict[sys.argv[1]])
    sys.exit(0)
