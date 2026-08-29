# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Tests for the GlobalPlugin wiring against the stubbed NVDA modules."""

from __future__ import annotations

import unittest
from unittest import mock

import config
import louisHelper
from globalPlugins import oxidizedBraille
from globalPlugins.oxidizedBraille import patch
from logHandler import log

from tests import TABLES_DIR


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
		self.originalTranslate.assert_not_called()

	def test_config_reset_clears_the_cache(self):
		spy = self.enterContext(mock.patch.object(self.plugin._patch, "clearCache"))
		config.post_configReset.notify(factoryDefaults=False)
		spy.assert_called_once_with()


class TestInstallFailure(unittest.TestCase):
	def test_failed_install_leaves_louis_helper_untouched(self):
		log.records.clear()
		originalTranslate = louisHelper.translate
		self.enterContext(
			mock.patch.object(patch.LouisHelperPatch, "install", side_effect=RuntimeError("no")),
		)
		plugin = oxidizedBraille.GlobalPlugin()
		self.assertIs(louisHelper.translate, originalTranslate)
		self.assertEqual(len(log.recordsAt("exception")), 1)
		plugin.terminate()
		self.assertEqual(config.post_configReset.handlers, [])


class TestCompile(unittest.TestCase):
	def test_resolves_names_like_nvda_and_compiles(self):
		compiled = oxidizedBraille._compile(["mini.ctb"], False)
		self.assertEqual(compiled.translate("abc"), "\u2801\u2803\u2809")

	def test_include_from_builtin_tables_resolves(self):
		compiled = oxidizedBraille._compile(["include.ctb"], False)
		self.assertEqual(compiled.translate("."), "\u2832")

	def test_unknown_table_raises_lookup_error(self):
		with self.assertRaises(LookupError):
			oxidizedBraille._compile(["missing.ctb"], False)

	def test_builtin_dir_is_nvdas_table_dir(self):
		import brailleTables

		self.assertEqual(brailleTables.TABLES_DIR, str(TABLES_DIR))
