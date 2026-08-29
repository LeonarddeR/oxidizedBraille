# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Routes NVDA's braille translation through louis-rs via the vendored louis_py package."""

from __future__ import annotations

import addonHandler
import brailleTables
import config
import globalPluginHandler
import louisHelper
from logHandler import log

from . import louis_py, patch, translator

addon = addonHandler.getCodeAddon()


def _compile(tables: tuple[str, ...], backward: bool) -> louis_py.Translator:
	"""Resolve table names the way NVDA does, then compile them for louis-rs."""
	paths = tuple(louisHelper._resolveTableInner(list(tables)))
	return translator.compileTranslator(paths, backward, brailleTables.TABLES_DIR)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super().__init__()
		self._patch: patch.LouisHelperPatch | None = None
		louisPatch = patch.LouisHelperPatch(_compile)
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

	def _onConfigReset(self) -> None:
		if self._patch is not None:
			self._patch.clearCache()

	def terminate(self):
		if self._patch is not None:
			config.post_configReset.unregister(self._onConfigReset)
			self._patch.uninstall(louisHelper)
			self._patch = None
		super().terminate()
