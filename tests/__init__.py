# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Unit test package bootstrap.

Importing this package prepares an environment in which ``globalPlugins.oxidizedBraille``
can be imported without a running NVDA instance:

* ``addon`` is put on ``sys.path`` so the plugin resolves as ``globalPlugins.oxidizedBraille``.
* Light-weight stand-ins for the NVDA modules the plugin imports are installed into
  ``sys.modules`` (see :mod:`tests._stubs`) before anything imports them.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADDON_DIR = REPO_ROOT / "addon"
TABLES_DIR = REPO_ROOT / "tests" / "tables"

sys.path.insert(0, str(ADDON_DIR))

from . import _stubs  # noqa: E402

_stubs.install()
