# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Routes NVDA's braille translation through louis-rs via the vendored louis_py package."""

from __future__ import annotations

import addonHandler
import config
import globalPluginHandler
import louisHelper
from logHandler import log

from . import louis_py, patch

addon = addonHandler.getCodeAddon()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super().__init__()
		self._patch: patch.LouisHelperPatch | None = None
		louisPatch = patch.LouisHelperPatch()
		try:
			louisPatch.install(louisHelper)
		except Exception:
			log.exception("Could not route braille translation through louis-rs; liblouis stays in use")
			return
		self._patch = louisPatch
		config.post_configReset.register(louisPatch.clearCache)
		log.info(
			f"Oxidized Braille Translation {addon.version}: louisHelper.translate and backTranslate "
			f"now use louis-rs (louis_py {louis_py.__version__})",
		)

	def terminate(self):
		if self._patch is not None:
			config.post_configReset.unregister(self._patch.clearCache)
			self._patch.uninstall(louisHelper)
			self._patch = None
		super().terminate()
