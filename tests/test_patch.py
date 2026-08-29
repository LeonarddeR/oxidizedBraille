# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Tests for the louisHelper replacement in ``patch``."""

from __future__ import annotations

import types
import unittest
from unittest import mock

from globalPlugins import oxidizedBraille
from globalPlugins.oxidizedBraille import louis_py, patch, translator
from logHandler import log

from tests._stubs import PanicException


def makeModule() -> types.SimpleNamespace:
	"""A louisHelper stand-in whose two functions record their calls."""
	return types.SimpleNamespace(
		translate=mock.Mock(return_value=("original",)),
		backTranslate=mock.Mock(return_value="original"),
	)


def work(compiled: object) -> str:
	return f"louis-rs via {compiled}"


def fallback() -> str:
	return "liblouis"


class TestFallback(unittest.TestCase):
	def setUp(self):
		log.records.clear()
		self.cache = mock.Mock(**{"get.return_value": "translator"})
		self.louisPatch = patch.LouisHelperPatch(self.cache)

	def test_success_uses_work_result(self):
		self.assertEqual(self.louisPatch._run(["a.ctb"], False, work, fallback), "louis-rs via translator")
		self.cache.get.assert_called_once_with(["a.ctb"], False)

	def test_table_parse_error_falls_back_and_logs_once(self):
		self.cache.get.side_effect = louis_py.TableParseError("bad table")
		for _ in range(2):
			self.assertEqual(self.louisPatch._run(["a.ctb"], False, work, fallback), "liblouis")
		self.assertEqual(len(log.records), 1)
		self.assertEqual(len(log.recordsAt("error")), 1)

	def test_failure_is_reported_per_direction(self):
		self.cache.get.side_effect = louis_py.TableParseError("bad table")
		self.louisPatch._run(["a.ctb"], False, work, fallback)
		self.louisPatch._run(["a.ctb"], True, work, fallback)
		self.assertEqual(len(log.recordsAt("error")), 2)

	def test_unresolvable_table_falls_back_and_logs_once(self):
		self.cache.get.side_effect = LookupError("no such table")
		for _ in range(2):
			self.assertEqual(self.louisPatch._run(["missing.ctb"], False, work, fallback), "liblouis")
		self.assertEqual(len(log.recordsAt("error")), 1)

	def test_translation_error_falls_back_and_logs_once(self):
		def failing(compiled: object) -> str:
			raise louis_py.TranslationError("boom")

		for _ in range(2):
			self.assertEqual(self.louisPatch._run(["a.ctb"], False, failing, fallback), "liblouis")
		self.assertEqual(len(log.recordsAt("exception")), 1)
		self.assertEqual(len(log.records), 1)

	def test_rust_panic_falls_back(self):
		def panicking(compiled: object) -> str:
			raise PanicException("boom")

		self.assertEqual(self.louisPatch._run(["a.ctb"], False, panicking, fallback), "liblouis")

	def test_keyboard_interrupt_propagates(self):
		def interrupting(compiled: object) -> str:
			raise KeyboardInterrupt

		with self.assertRaises(KeyboardInterrupt):
			self.louisPatch._run(["a.ctb"], False, interrupting, fallback)

	def test_clear_cache_clears_cache_and_reports_again(self):
		self.cache.get.side_effect = louis_py.TableParseError("bad table")
		self.louisPatch._run(["a.ctb"], False, work, fallback)
		self.louisPatch.clearCache()
		self.louisPatch._run(["a.ctb"], False, work, fallback)
		self.cache.clear.assert_called_once_with()
		self.assertEqual(len(log.recordsAt("error")), 2)


class PatchTestCase(unittest.TestCase):
	"""A patch installed on a louisHelper stand-in, compiling the fixture tables for real."""

	def setUp(self):
		log.records.clear()
		self.module = makeModule()
		self.originalTranslate = self.module.translate
		self.originalBackTranslate = self.module.backTranslate
		self.louisPatch = patch.LouisHelperPatch(translator.TranslatorCache(oxidizedBraille._compile))
		self.louisPatch.install(self.module)


class TestTranslate(PatchTestCase):
	def test_returns_louis_rs_cells_without_calling_the_original(self):
		self.assertEqual(self.module.translate(["mini.ctb"], "abc"), ([1, 3, 9], [0, 1, 2], [0, 1, 2], None))
		self.originalTranslate.assert_not_called()

	def test_cursor_is_translated(self):
		self.assertEqual(self.module.translate(["mini.ctb"], "abc", cursorPos=1)[3], 1)

	def test_null_characters_are_stripped_before_translation(self):
		cells, _, rawToBraillePos, _ = self.module.translate(["mini.ctb"], "a\0b")
		self.assertEqual(cells, [1, 3])
		self.assertEqual(rawToBraillePos, [0, 1])

	def test_typeform_length_mismatch_does_not_raise(self):
		self.assertEqual(self.module.translate(["mini.ctb"], "abc", typeform=[1])[0], [1, 3, 9])

	def test_mode_and_typeform_are_mapped_for_louis_rs(self):
		spy = self.enterContext(
			mock.patch.object(translator, "translateText", return_value=([], [], [], None)),
		)
		self.module.translate(["mini.ctb"], "abc", typeform=[1, 0, 0], mode=2)
		kwargs = spy.call_args.kwargs
		self.assertEqual(kwargs["mode"], louis_py.TranslationMode.COMPBRL_AT_CURSOR)
		self.assertEqual(kwargs["emphasis"], [("italic", 0, 1)])

	def test_broken_table_falls_back_with_untouched_arguments(self):
		result = self.module.translate(["broken.ctb"], "a\0b", typeform=None, cursorPos=1, mode=2)
		self.assertEqual(result, ("original",))
		self.originalTranslate.assert_called_once_with(["broken.ctb"], "a\0b", None, 1, 2)

	def test_position_error_falls_back(self):
		self.enterContext(
			mock.patch.object(translator, "translateText", side_effect=translator.PositionError("x")),
		)
		self.assertEqual(self.module.translate(["mini.ctb"], "abc"), ("original",))


class TestBackTranslate(PatchTestCase):
	def test_round_trip_through_louis_rs(self):
		cells = self.module.translate(["mini.ctb"], "abc")[0]
		self.assertEqual(self.module.backTranslate(["mini.ctb"], cells), "abc")
		self.originalBackTranslate.assert_not_called()

	def test_escaped_undefined_cells_are_dropped(self):
		self.assertEqual(self.module.backTranslate(["mini.ctb"], [1, 0x3F, 3]), "ab")

	def test_no_cells_give_empty_string(self):
		self.assertEqual(self.module.backTranslate(["mini.ctb"], []), "")

	def test_mode_is_mapped_and_undefined_cells_are_suppressed(self):
		spy = self.enterContext(mock.patch.object(translator, "backTranslateCells", return_value=""))
		self.module.backTranslate(["mini.ctb"], [1], mode=256)
		self.assertEqual(
			spy.call_args.kwargs["mode"],
			louis_py.TranslationMode.PARTIAL_TRANS | louis_py.TranslationMode.NO_UNDEFINED,
		)

	def test_broken_table_falls_back_with_the_same_arguments(self):
		self.assertEqual(self.module.backTranslate(["broken.ctb"], [1, 3], mode=256), "original")
		self.originalBackTranslate.assert_called_once_with(["broken.ctb"], [1, 3], 256)


class TestInstall(unittest.TestCase):
	def setUp(self):
		log.records.clear()
		self.cache = mock.Mock()
		self.louisPatch = patch.LouisHelperPatch(self.cache)
		self.module = makeModule()
		self.originalTranslate = self.module.translate
		self.originalBackTranslate = self.module.backTranslate

	def test_install_replaces_both_functions_with_bound_methods(self):
		self.louisPatch.install(self.module)
		self.assertIs(self.module.translate.__self__, self.louisPatch)
		self.assertIs(self.module.backTranslate.__self__, self.louisPatch)

	def test_uninstall_restores_both_functions_and_clears_the_cache(self):
		self.louisPatch.install(self.module)
		self.louisPatch.uninstall(self.module)
		self.assertIs(self.module.translate, self.originalTranslate)
		self.assertIs(self.module.backTranslate, self.originalBackTranslate)
		self.cache.clear.assert_called_once_with()

	def test_double_install_raises(self):
		self.louisPatch.install(self.module)
		with self.assertRaises(RuntimeError):
			self.louisPatch.install(self.module)

	def test_install_over_another_patch_raises(self):
		self.louisPatch.install(self.module)
		with self.assertRaises(RuntimeError):
			patch.LouisHelperPatch(mock.Mock()).install(self.module)

	def test_uninstall_leaves_a_foreign_replacement_alone_and_warns(self):
		self.louisPatch.install(self.module)
		foreign = mock.Mock()
		self.module.translate = foreign
		self.louisPatch.uninstall(self.module)
		self.assertIs(self.module.translate, foreign)
		self.assertIs(self.module.backTranslate, self.originalBackTranslate)
		self.assertEqual(len(log.recordsAt("warning")), 1)

	def test_uninstall_without_install_leaves_the_module_alone(self):
		self.louisPatch.uninstall(self.module)
		self.assertIs(self.module.translate, self.originalTranslate)
