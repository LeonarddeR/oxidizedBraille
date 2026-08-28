# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""The vendored louis_py package loads through the add-on package."""

from __future__ import annotations

import os
import unittest

from tests import TABLES_DIR


class TestVendoredLouisPy(unittest.TestCase):
	def test_package_exposes_version(self):
		from globalPlugins.oxidizedBraille import louis_py

		self.assertIsInstance(louis_py.__version__, str)

	def test_translation_mode_flags_present(self):
		from globalPlugins.oxidizedBraille import louis_py

		self.assertTrue(louis_py.TranslationMode.PARTIAL_TRANS)
		self.assertTrue(louis_py.TranslationMode.NO_UNDEFINED)

	def test_translator_uses_louis_table_path(self):
		from globalPlugins.oxidizedBraille import louis_py

		os.environ["LOUIS_TABLE_PATH"] = str(TABLES_DIR)
		self.addCleanup(os.environ.pop, "LOUIS_TABLE_PATH", None)
		translator = louis_py.Translator(["mini.ctb"])
		self.assertEqual(translator.translate("abc"), "\u2801\u2803\u2809")
