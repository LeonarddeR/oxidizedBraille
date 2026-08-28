# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Tests for the GlobalPlugin wiring against the stubbed NVDA modules."""

from __future__ import annotations

import unittest

import brailleTables
import config
import louisHelper
from globalPlugins import oxidizedBraille
from globalPlugins.oxidizedBraille import patch
from logHandler import log

from tests import TABLES_DIR
from tests._stubs import SpyFunction


class TestGlobalPlugin(unittest.TestCase):
	def setUp(self):
		log.records.clear()
		self.originalTranslate = louisHelper.translate
		self.originalBackTranslate = louisHelper.backTranslate
		self.plugin = oxidizedBraille.GlobalPlugin()
		self.addCleanup(self.plugin.terminate)

	def test_init_patches_louis_helper(self):
		self.assertIsInstance(louisHelper.translate.__self__, patch.LouisHelperPatch)
		self.assertIsInstance(louisHelper.backTranslate.__self__, patch.LouisHelperPatch)

	def test_init_registers_for_config_reset(self):
		self.assertIn(self.plugin._onConfigReset, config.post_configReset.handlers)

	def test_init_logs_the_engine_switch(self):
		self.assertTrue(any("louis-rs" in message for message in log.recordsAt("info")))

	def test_terminate_restores_louis_helper_and_unregisters(self):
		self.plugin.terminate()
		self.assertIs(louisHelper.translate, self.originalTranslate)
		self.assertIs(louisHelper.backTranslate, self.originalBackTranslate)
		self.assertEqual(config.post_configReset.handlers, [])

	def test_translation_through_louis_helper_uses_louis_rs(self):
		self.assertEqual(louisHelper.translate(["mini.ctb"], "abc")[0], [1, 3, 9])
		self.assertEqual(louisHelper.backTranslate(["mini.ctb"], [1, 3]), "ab")
		self.assertEqual(self.originalTranslate.calls, [])

	def test_config_reset_clears_the_cache(self):
		spy = SpyFunction(None)
		self.plugin._patch.clearCache = spy
		config.post_configReset.notify(factoryDefaults=False)
		self.assertEqual(len(spy.calls), 1)


class TestInstallFailure(unittest.TestCase):
	def test_failed_install_leaves_louis_helper_untouched(self):
		log.records.clear()
		originalTranslate = louisHelper.translate

		def failingInstall(self: patch.LouisHelperPatch, module: object) -> None:
			raise RuntimeError("no patching today")

		self.addCleanup(setattr, patch.LouisHelperPatch, "install", patch.LouisHelperPatch.install)
		patch.LouisHelperPatch.install = failingInstall
		plugin = oxidizedBraille.GlobalPlugin()
		self.assertIs(louisHelper.translate, originalTranslate)
		self.assertEqual(len(log.recordsAt("exception")), 1)
		plugin.terminate()
		self.assertEqual(config.post_configReset.handlers, [])


class TestSearchDirs(unittest.TestCase):
	def setUp(self):
		self.addCleanup(brailleTables._tablesDirs.maps[0].clear)

	def test_custom_dirs_list_scratchpad_first_then_addons_skipping_missing(self):
		testsDir = str(TABLES_DIR.parent)
		brailleTables._tablesDirs["someAddon"] = testsDir
		brailleTables._tablesDirs["missingAddon"] = "C:/does-not-exist"
		brailleTables._tablesDirs[brailleTables.TableSource.SCRATCHPAD] = str(TABLES_DIR)
		self.assertEqual(oxidizedBraille._customTableDirs(), [str(TABLES_DIR), testsDir])

	def test_search_dirs_start_with_the_table_dir_and_end_with_builtin(self):
		testsDir = str(TABLES_DIR.parent)
		brailleTables._tablesDirs["someAddon"] = testsDir
		self.assertEqual(
			oxidizedBraille._getSearchDirs(("C:/tables/x.ctb",)),
			("C:/tables", testsDir, str(TABLES_DIR)),
		)

	def test_resolve_tables_gives_absolute_paths(self):
		self.assertEqual(oxidizedBraille._resolveTables(["mini.ctb"]), (str(TABLES_DIR / "mini.ctb"),))
