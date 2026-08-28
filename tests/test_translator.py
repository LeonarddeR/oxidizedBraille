# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Tests for table lookup and translator caching in ``translator``."""

from __future__ import annotations

import os
import unittest
from dataclasses import dataclass

from globalPlugins.oxidizedBraille import louis_py, translator
from logHandler import log

from tests import TABLES_DIR

TABLES = str(TABLES_DIR)
MINI = str(TABLES_DIR / "mini.ctb")
INCLUDE = str(TABLES_DIR / "include.ctb")
BROKEN = str(TABLES_DIR / "broken.ctb")
BOGUS_DIR = "C:/does-not-exist"


class TestBuildSearchDirs(unittest.TestCase):
	def test_table_dirs_come_first_then_custom_then_builtin(self):
		self.assertEqual(
			translator.buildSearchDirs(["C:/a/x.ctb", "C:/b/y.ctb"], ["C:/custom"], "C:/builtin"),
			("C:/a", "C:/b", "C:/custom", "C:/builtin"),
		)

	def test_duplicates_are_removed_keeping_the_first(self):
		self.assertEqual(
			translator.buildSearchDirs(["C:/builtin/x.ctb"], ["C:/builtin"], "C:/builtin"),
			("C:/builtin",),
		)

	def test_result_is_never_empty(self):
		self.assertEqual(translator.buildSearchDirs([], [], "C:/builtin"), ("C:/builtin",))


class TestTablePath(unittest.TestCase):
	def setUp(self):
		self.previous = os.environ.pop(translator.TABLE_PATH_VARIABLE, None)

	def tearDown(self):
		os.environ.pop(translator.TABLE_PATH_VARIABLE, None)
		if self.previous is not None:
			os.environ[translator.TABLE_PATH_VARIABLE] = self.previous

	def test_sets_variable_to_joined_dirs(self):
		with translator.tablePath(["C:/a", "C:/b"]):
			self.assertEqual(os.environ[translator.TABLE_PATH_VARIABLE], os.pathsep.join(["C:/a", "C:/b"]))

	def test_restores_previous_value(self):
		os.environ[translator.TABLE_PATH_VARIABLE] = "C:/before"
		with translator.tablePath(["C:/a"]):
			pass
		self.assertEqual(os.environ[translator.TABLE_PATH_VARIABLE], "C:/before")

	def test_removes_variable_that_was_unset(self):
		with translator.tablePath(["C:/a"]):
			pass
		self.assertNotIn(translator.TABLE_PATH_VARIABLE, os.environ)

	def test_rejects_empty_list(self):
		with self.assertRaises(ValueError), translator.tablePath([]):
			pass

	def test_absolute_table_compiles_with_bogus_search_path(self):
		with translator.tablePath([BOGUS_DIR]):
			self.assertEqual(louis_py.Translator([MINI]).translate("a"), "\u2801")


class TestTranslatorCache(unittest.TestCase):
	def setUp(self):
		self.cache = translator.TranslatorCache(maxSize=2)
		log.records.clear()

	def test_same_key_returns_same_object(self):
		first = self.cache.get([MINI], [TABLES], backward=False)
		second = self.cache.get([MINI], [TABLES], backward=False)
		self.assertIs(first, second)

	def test_backward_gives_different_object(self):
		forward = self.cache.get([MINI], [TABLES], backward=False)
		backward = self.cache.get([MINI], [TABLES], backward=True)
		self.assertIsNot(forward, backward)
		self.assertEqual(backward.translate("\u2801"), "a")

	def test_different_search_dirs_give_different_object(self):
		first = self.cache.get([MINI], [TABLES], backward=False)
		second = self.cache.get([MINI], [BOGUS_DIR, TABLES], backward=False)
		self.assertIsNot(first, second)

	def test_oldest_entry_is_evicted_beyond_max_size(self):
		first = self.cache.get([MINI], [TABLES], backward=False)
		self.cache.get([MINI], [TABLES], backward=True)
		self.cache.get([INCLUDE], [TABLES], backward=False)
		self.assertEqual(len(self.cache), 2)
		self.assertIsNot(self.cache.get([MINI], [TABLES], backward=False), first)

	def test_clear_drops_entries(self):
		first = self.cache.get([MINI], [TABLES], backward=False)
		self.cache.clear()
		self.assertEqual(len(self.cache), 0)
		self.assertIsNot(self.cache.get([MINI], [TABLES], backward=False), first)

	def test_include_compiles_when_its_dir_is_searched(self):
		including = self.cache.get([INCLUDE], [TABLES], backward=False)
		self.assertEqual(including.translate("a."), "\u2801\u2832")

	def test_include_fails_without_its_dir(self):
		with self.assertRaises(louis_py.TableParseError):
			self.cache.get([INCLUDE], [BOGUS_DIR], backward=False)

	def test_broken_table_raises_with_errors(self):
		with self.assertRaises(louis_py.TableParseError) as context:
			self.cache.get([BROKEN], [TABLES], backward=False)
		self.assertTrue(context.exception.errors)

	def test_failed_compile_is_not_cached(self):
		with self.assertRaises(louis_py.TableParseError):
			self.cache.get([BROKEN], [TABLES], backward=False)
		self.assertEqual(len(self.cache), 0)

	def test_compile_is_logged_at_debug_only_on_a_miss(self):
		self.cache.get([MINI], [TABLES], backward=False)
		self.assertEqual(len(log.recordsAt("debug")), 1)
		self.cache.get([MINI], [TABLES], backward=False)
		self.assertEqual(len(log.recordsAt("debug")), 1)


class TestIsRecoverable(unittest.TestCase):
	def test_ordinary_exception_is_recoverable(self):
		self.assertTrue(translator.isRecoverable(ValueError("x")))

	def test_rust_panic_is_recoverable(self):
		class PanicException(BaseException):
			pass

		self.assertTrue(translator.isRecoverable(PanicException("boom")))

	def test_keyboard_interrupt_is_not_recoverable(self):
		self.assertFalse(translator.isRecoverable(KeyboardInterrupt()))


@dataclass
class FakeResult:
	output: str
	input_positions: list[int]
	output_positions: list[int]
	cursor_pos: int | None


class FakeTranslator:
	def __init__(self, result: FakeResult):
		self.result = result

	def translate_with_options(self, text: str, **kwargs: object) -> FakeResult:
		return self.result


class TestTranslateText(unittest.TestCase):
	def setUp(self):
		log.records.clear()
		with translator.tablePath([TABLES]):
			self.mini = louis_py.Translator([MINI])

	def translate(self, text: str, cursorPos: int | None = None):
		return translator.translateText(self.mini, text, mode=0, emphasis=[], cursorPos=cursorPos)

	def test_returns_cells_positions_and_cursor(self):
		self.assertEqual(self.translate("abc", cursorPos=1), ([1, 3, 9], [0, 1, 2], [0, 1, 2], 1))

	def test_cursor_none_stays_none(self):
		self.assertIsNone(self.translate("abc")[3])

	def test_cursor_past_end_maps_to_end_of_cells(self):
		self.assertEqual(self.translate("abc", cursorPos=10)[3], 3)

	def test_negative_cursor_is_clamped_to_start(self):
		self.assertEqual(self.translate("abc", cursorPos=-1)[3], 0)

	def test_empty_text_gives_empty_lists(self):
		self.assertEqual(self.translate("", cursorPos=0), ([], [], [], 0))

	def test_undefined_character_keeps_lists_aligned(self):
		cells, brailleToRawPos, rawToBraillePos, _ = self.translate("a1c")
		self.assertTrue(all(0 <= cell <= 0xFF for cell in cells))
		self.assertEqual(len(brailleToRawPos), len(cells))
		self.assertEqual(len(rawToBraillePos), 3)

	def test_mismatched_position_lists_raise_position_error(self):
		fake = FakeTranslator(FakeResult("\u2801\u2803", [0], [0, 1], None))
		with self.assertRaises(translator.PositionError):
			translator.translateText(fake, "ab", mode=0, emphasis=[], cursorPos=None)

	def test_position_error_is_a_louis_error(self):
		self.assertTrue(issubclass(translator.PositionError, louis_py.LouisError))

	def test_non_braille_output_becomes_full_cells_and_is_logged(self):
		fake = FakeTranslator(FakeResult("\u2801x", [0, 1], [0, 1], None))
		cells, _, _, _ = translator.translateText(fake, "ab", mode=0, emphasis=[], cursorPos=None)
		self.assertEqual(cells, [1, 0xFF])
		self.assertEqual(len(log.recordsAt("debug")), 1)
