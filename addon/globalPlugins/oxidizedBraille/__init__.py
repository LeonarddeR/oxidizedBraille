# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Routes NVDA's braille translation through louis-rs via the vendored louis_py package."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import addonHandler
import brailleTables
import config
import globalPluginHandler
import louisHelper
from logHandler import log

from . import louis_py, patch, translator

addon = addonHandler.getCodeAddon()

MODE_MAP = {
	int(louisHelper.TranslationMode.COMPBRL_AT_CURSOR): int(louis_py.TranslationMode.COMPBRL_AT_CURSOR),
	int(louisHelper.TranslationMode.PARTIAL_TRANS): int(louis_py.TranslationMode.PARTIAL_TRANS),
}
"""NVDA translation mode bits and the louis-rs mode bits they map to."""

TYPEFORM_CLASSES = {
	int(louisHelper.Typeform.ITALIC): "italic",
	int(louisHelper.Typeform.BOLD): "bold",
	int(louisHelper.Typeform.UNDERLINE): "underline",
}
"""NVDA typeform bits and the louis-rs emphasis classes they map to."""


def _resolveTables(tableList: list[str]) -> tuple[str, ...]:
	return tuple(louisHelper._resolveTableInner(tableList))


def _customTableDirs() -> list[str]:
	"""Scratchpad and add-on table directories NVDA knows about, scratchpad first, existing ones only."""
	custom = brailleTables._tablesDirs.maps[0]
	scratchpad = custom.get(brailleTables.TableSource.SCRATCHPAD)
	ordered = [scratchpad] if scratchpad else []
	ordered.extend(
		directory for source, directory in custom.items() if source != brailleTables.TableSource.SCRATCHPAD
	)
	return [directory for directory in ordered if os.path.isdir(directory)]


def _getSearchDirs(tables: Sequence[str]) -> tuple[str, ...]:
	return translator.buildSearchDirs(tables, _customTableDirs(), brailleTables.TABLES_DIR)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super().__init__()
		self._patch: patch.LouisHelperPatch | None = None
		louisPatch = patch.LouisHelperPatch(
			cache=translator.TranslatorCache(),
			resolveTables=_resolveTables,
			getSearchDirs=_getSearchDirs,
			modeMap=MODE_MAP,
			typeformClasses=TYPEFORM_CLASSES,
		)
		try:
			louisPatch.install(louisHelper)
		except Exception:
			log.exception("Could not route braille translation through louis-rs; liblouis stays in use")
			return
		self._patch = louisPatch
		config.post_configReset.register(self._onConfigReset)
		log.info(
			f"Oxidized Braille Translation {addon.version}: louisHelper.translate and backTranslate "
			f"now use louis-rs (louis_py {louis_py.__version__})",
		)

	def _onConfigReset(self, **_kwargs: Any) -> None:
		if self._patch is not None:
			self._patch.clearCache()

	def terminate(self):
		if self._patch is not None:
			config.post_configReset.unregister(self._onConfigReset)
			self._patch.uninstall(louisHelper)
			self._patch = None
		super().terminate()
