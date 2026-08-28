# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Tests for the louisHelper replacement in ``patch``."""

from __future__ import annotations

import types
import unittest
from typing import Any

from globalPlugins.oxidizedBraille import louis_py, patch
from logHandler import log

from tests._stubs import SpyFunction

MODE_MAP = {
	2: int(louis_py.TranslationMode.COMPBRL_AT_CURSOR),
	256: int(louis_py.TranslationMode.PARTIAL_TRANS),
}
CLASSES = {1: "italic", 4: "bold", 2: "underline"}


class PanicException(BaseException):
	"""Stands in for pyo3_runtime.PanicException, matched by name."""


class FakeCache:
	"""Records requests; returns a sentinel translator or raises the configured error."""

	def __init__(self, error: BaseException | None = None):
		self.error = error
		self.calls: list[tuple[tuple[str, ...], tuple[str, ...], bool]] = []
		self.cleared = 0

	def get(self, tables: Any, searchDirs: Any, backward: bool) -> object:
		self.calls.append((tuple(tables), tuple(searchDirs), backward))
		if self.error is not None:
			raise self.error
		return "translator"

	def clear(self):
		self.cleared += 1


def makePatch(cache: FakeCache, resolveTables: Any = tuple) -> patch.LouisHelperPatch:
	return patch.LouisHelperPatch(
		cache=cache,
		resolveTables=resolveTables,
		getSearchDirs=lambda tables: ("dir-of-" + tables[0],),
		modeMap=MODE_MAP,
		typeformClasses=CLASSES,
	)


def work(translator: object) -> str:
	return f"louis-rs via {translator}"


def fallback() -> str:
	return "liblouis"


def raising(error: BaseException) -> Any:
	def work(translator: object) -> str:
		raise error

	return work


class TestFallback(unittest.TestCase):
	def setUp(self):
		log.records.clear()

	def test_success_uses_work_result(self):
		cache = FakeCache()
		self.assertEqual(makePatch(cache)._run(["a.ctb"], False, work, fallback), "louis-rs via translator")
		self.assertEqual(cache.calls, [(("a.ctb",), ("dir-of-a.ctb",), False)])

	def test_table_parse_error_falls_back_and_logs_once(self):
		cache = FakeCache(louis_py.TableParseError("bad table"))
		louisPatch = makePatch(cache)
		self.assertEqual(louisPatch._run(["a.ctb"], False, work, fallback), "liblouis")
		self.assertEqual(len(log.recordsAt("error")), 1)
		self.assertEqual(louisPatch._run(["a.ctb"], False, work, fallback), "liblouis")
		self.assertEqual(len(cache.calls), 1)
		self.assertEqual(len(log.records), 1)

	def test_broken_key_is_per_direction(self):
		cache = FakeCache(louis_py.TableParseError("bad table"))
		louisPatch = makePatch(cache)
		louisPatch._run(["a.ctb"], False, work, fallback)
		louisPatch._run(["a.ctb"], True, work, fallback)
		self.assertEqual(len(cache.calls), 2)

	def test_unresolvable_table_falls_back_and_logs_once(self):
		def resolveTables(tables: list[str]) -> tuple[str, ...]:
			raise LookupError("no such table")

		cache = FakeCache()
		louisPatch = makePatch(cache, resolveTables)
		self.assertEqual(louisPatch._run(["missing.ctb"], False, work, fallback), "liblouis")
		self.assertEqual(louisPatch._run(["missing.ctb"], False, work, fallback), "liblouis")
		self.assertEqual(cache.calls, [])
		self.assertEqual(len(log.recordsAt("error")), 1)

	def test_translation_error_falls_back_without_marking(self):
		cache = FakeCache()
		louisPatch = makePatch(cache)
		error = louis_py.TranslationError("boom")
		self.assertEqual(louisPatch._run(["a.ctb"], False, raising(error), fallback), "liblouis")
		self.assertEqual(louisPatch._run(["a.ctb"], False, raising(error), fallback), "liblouis")
		self.assertEqual(len(cache.calls), 2)
		self.assertEqual(len(log.recordsAt("exception")), 1)
		self.assertEqual(len(log.recordsAt("debug")), 1)

	def test_rust_panic_falls_back(self):
		louisPatch = makePatch(FakeCache())
		self.assertEqual(
			louisPatch._run(["a.ctb"], False, raising(PanicException("boom")), fallback),
			"liblouis",
		)

	def test_keyboard_interrupt_propagates(self):
		louisPatch = makePatch(FakeCache())
		with self.assertRaises(KeyboardInterrupt):
			louisPatch._run(["a.ctb"], False, raising(KeyboardInterrupt()), fallback)

	def test_clear_cache_re_enables_broken_key(self):
		cache = FakeCache(louis_py.TableParseError("bad table"))
		louisPatch = makePatch(cache)
		louisPatch._run(["a.ctb"], False, work, fallback)
		louisPatch.clearCache()
		louisPatch._run(["a.ctb"], False, work, fallback)
		self.assertEqual(len(cache.calls), 2)
		self.assertEqual(cache.cleared, 1)


class PatchTestCase(unittest.TestCase):
	def setUp(self):
		import louisHelper
		from globalPlugins.oxidizedBraille import translator

		from tests import TABLES_DIR

		log.records.clear()
		self.originalTranslate = SpyFunction(("original",))
		self.originalBackTranslate = SpyFunction("original")
		self.louisPatch = patch.LouisHelperPatch(
			cache=translator.TranslatorCache(),
			resolveTables=lambda tables: tuple(louisHelper._resolveTableInner(tables)),
			getSearchDirs=lambda tables: translator.buildSearchDirs(tables, [], str(TABLES_DIR)),
			modeMap=MODE_MAP,
			typeformClasses=CLASSES,
		)
		self.louisPatch._original = (self.originalTranslate, self.originalBackTranslate)
		self.translator = translator


class TestTranslate(PatchTestCase):
	def test_returns_louis_rs_cells_without_calling_the_original(self):
		self.assertEqual(
			self.louisPatch.translate(["mini.ctb"], "abc"),
			([1, 3, 9], [0, 1, 2], [0, 1, 2], None),
		)
		self.assertEqual(self.originalTranslate.calls, [])

	def test_cursor_is_translated(self):
		self.assertEqual(self.louisPatch.translate(["mini.ctb"], "abc", cursorPos=1)[3], 1)

	def test_null_characters_are_stripped_before_translation(self):
		cells, brailleToRawPos, rawToBraillePos, _ = self.louisPatch.translate(["mini.ctb"], "a\0b")
		self.assertEqual(cells, [1, 3])
		self.assertEqual(rawToBraillePos, [0, 1])

	def test_typeform_length_mismatch_does_not_raise(self):
		self.assertEqual(self.louisPatch.translate(["mini.ctb"], "abc", typeform=[1])[0], [1, 3, 9])

	def test_mode_and_typeform_are_mapped_for_louis_rs(self):
		spy = SpyFunction(([], [], [], None))
		self.addCleanup(setattr, self.translator, "translateText", self.translator.translateText)
		self.translator.translateText = spy
		self.louisPatch.translate(["mini.ctb"], "abc", typeform=[1, 0, 0], mode=2)
		kwargs = spy.calls[0][1]
		self.assertEqual(kwargs["mode"], int(louis_py.TranslationMode.COMPBRL_AT_CURSOR))
		self.assertEqual(kwargs["emphasis"], [("italic", 0, 1)])

	def test_broken_table_falls_back_with_untouched_arguments(self):
		result = self.louisPatch.translate(["broken.ctb"], "a\0b", typeform=None, cursorPos=1, mode=2)
		self.assertEqual(result, ("original",))
		self.assertEqual(self.originalTranslate.calls, [((["broken.ctb"], "a\0b", None, 1, 2), {})])

	def test_position_error_falls_back(self):
		def failing(*args: Any, **kwargs: Any) -> Any:
			raise self.translator.PositionError("mismatch")

		self.addCleanup(setattr, self.translator, "translateText", self.translator.translateText)
		self.translator.translateText = failing
		self.assertEqual(self.louisPatch.translate(["mini.ctb"], "abc"), ("original",))


class TestBackTranslate(PatchTestCase):
	def test_round_trip_through_louis_rs(self):
		cells = self.louisPatch.translate(["mini.ctb"], "abc")[0]
		self.assertEqual(self.louisPatch.backTranslate(["mini.ctb"], cells), "abc")
		self.assertEqual(self.originalBackTranslate.calls, [])

	def test_escaped_undefined_cells_are_dropped(self):
		self.assertEqual(self.louisPatch.backTranslate(["mini.ctb"], [1, 0x3F, 3]), "ab")

	def test_no_cells_give_empty_string(self):
		self.assertEqual(self.louisPatch.backTranslate(["mini.ctb"], []), "")

	def test_mode_is_mapped_and_undefined_cells_are_suppressed(self):
		spy = SpyFunction("")
		self.addCleanup(setattr, self.translator, "backTranslateCells", self.translator.backTranslateCells)
		self.translator.backTranslateCells = spy
		self.louisPatch.backTranslate(["mini.ctb"], [1], mode=256)
		self.assertEqual(
			spy.calls[0][1]["mode"],
			int(louis_py.TranslationMode.PARTIAL_TRANS | louis_py.TranslationMode.NO_UNDEFINED),
		)

	def test_broken_table_falls_back_with_the_same_arguments(self):
		self.assertEqual(self.louisPatch.backTranslate(["broken.ctb"], [1, 3], mode=256), "original")
		self.assertEqual(self.originalBackTranslate.calls, [((["broken.ctb"], [1, 3], 256), {})])


class TestInstall(unittest.TestCase):
	def setUp(self):
		log.records.clear()
		self.cache = FakeCache()
		self.louisPatch = makePatch(self.cache)
		self.originalTranslate = SpyFunction(("original",))
		self.originalBackTranslate = SpyFunction("original")
		self.module = types.SimpleNamespace(
			translate=self.originalTranslate,
			backTranslate=self.originalBackTranslate,
		)

	def test_install_replaces_both_functions_with_bound_methods(self):
		self.louisPatch.install(self.module)
		self.assertIs(self.module.translate.__self__, self.louisPatch)
		self.assertIs(self.module.backTranslate.__self__, self.louisPatch)

	def test_uninstall_restores_both_functions_and_clears_the_cache(self):
		self.louisPatch.install(self.module)
		self.louisPatch.uninstall(self.module)
		self.assertIs(self.module.translate, self.originalTranslate)
		self.assertIs(self.module.backTranslate, self.originalBackTranslate)
		self.assertEqual(self.cache.cleared, 1)

	def test_double_install_raises(self):
		self.louisPatch.install(self.module)
		with self.assertRaises(RuntimeError):
			self.louisPatch.install(self.module)

	def test_install_over_another_patch_raises(self):
		self.louisPatch.install(self.module)
		with self.assertRaises(RuntimeError):
			makePatch(FakeCache()).install(self.module)

	def test_uninstall_leaves_a_foreign_replacement_alone_and_warns(self):
		self.louisPatch.install(self.module)
		foreign = SpyFunction(None)
		self.module.translate = foreign
		self.louisPatch.uninstall(self.module)
		self.assertIs(self.module.translate, foreign)
		self.assertIs(self.module.backTranslate, self.originalBackTranslate)
		self.assertEqual(len(log.recordsAt("warning")), 1)

	def test_uninstall_without_install_is_a_no_op(self):
		self.louisPatch.uninstall(self.module)
		self.assertIs(self.module.translate, self.originalTranslate)


class TestInstalledTranslation(PatchTestCase):
	def test_calls_through_the_module_reach_louis_rs(self):
		self.louisPatch._original = None
		module = types.SimpleNamespace(
			translate=self.originalTranslate,
			backTranslate=self.originalBackTranslate,
		)
		self.louisPatch.install(module)
		self.assertEqual(module.translate(["mini.ctb"], "abc")[0], [1, 3, 9])
		self.assertEqual(module.backTranslate(["mini.ctb"], [1, 3]), "ab")
		self.assertEqual(self.originalTranslate.calls, [])
