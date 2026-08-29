# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Tests for table lookup, translator caching and result shaping in ``translator``."""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from globalPlugins.oxidizedBraille import louis_py, translator
from logHandler import log

from tests import TABLES_DIR
from tests._stubs import PanicException

TABLES = str(TABLES_DIR)
MINI = str(TABLES_DIR / "mini.ctb")
INCLUDE = str(TABLES_DIR / "include.ctb")
BROKEN = str(TABLES_DIR / "broken.ctb")
BOGUS_DIR = "C:/does-not-exist"


class TestBuildSearchDirs(unittest.TestCase):
	def test_table_dirs_come_first_then_builtin(self):
		self.assertEqual(
			translator.buildSearchDirs(["C:/a/x.ctb", "C:/b/y.ctb"], "C:/builtin"),
			("C:/a", "C:/b", "C:/builtin"),
		)

	def test_duplicates_are_removed_keeping_the_first(self):
		self.assertEqual(translator.buildSearchDirs(["C:/builtin/x.ctb"], "C:/builtin"), ("C:/builtin",))


class TestTablePath(unittest.TestCase):
	def setUp(self):
		self.enterContext(mock.patch.dict(os.environ))
		os.environ.pop(translator.TABLE_PATH_VARIABLE, None)

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


class TestCompileTranslator(unittest.TestCase):
	def test_compiles_forward_and_backward(self):
		forward = translator.compileTranslator([MINI], False, BOGUS_DIR)
		backward = translator.compileTranslator([MINI], True, BOGUS_DIR)
		self.assertEqual(forward.translate("ab"), "\u2801\u2803")
		self.assertEqual(backward.translate("\u2801\u2803"), "ab")

	def test_include_next_to_the_table_resolves_without_builtin_dir(self):
		including = translator.compileTranslator([INCLUDE], False, BOGUS_DIR)
		self.assertEqual(including.translate("a."), "\u2801\u2832")

	def test_include_from_builtin_dir_resolves_only_when_given(self):
		with tempfile.TemporaryDirectory() as directory:
			table = Path(directory) / "custom.ctb"
			table.write_text("include mini.ctb\n", encoding="utf-8")
			self.assertEqual(
				translator.compileTranslator([str(table)], False, TABLES).translate("a"),
				"\u2801",
			)
			with self.assertRaises(louis_py.TableParseError):
				translator.compileTranslator([str(table)], False, BOGUS_DIR)

	def test_broken_table_raises_with_errors(self):
		with self.assertRaises(louis_py.TableParseError) as context:
			translator.compileTranslator([BROKEN], False, TABLES)
		self.assertTrue(context.exception.errors)


class TestTranslatorCache(unittest.TestCase):
	def setUp(self):
		log.records.clear()
		self.compile = mock.Mock(side_effect=self.compileTable)
		self.cache = translator.TranslatorCache(self.compile, maxSize=2)

	@staticmethod
	def compileTable(tableList: list[str], backward: bool) -> louis_py.Translator:
		return translator.compileTranslator([str(TABLES_DIR / name) for name in tableList], backward, TABLES)

	def test_same_key_returns_same_object_without_recompiling(self):
		first = self.cache.get(["mini.ctb"], backward=False)
		self.assertIs(self.cache.get(["mini.ctb"], backward=False), first)
		self.assertEqual(self.compile.call_count, 1)

	def test_backward_gives_different_object(self):
		forward = self.cache.get(["mini.ctb"], backward=False)
		backward = self.cache.get(["mini.ctb"], backward=True)
		self.assertIsNot(forward, backward)
		self.assertEqual(backward.translate("\u2801"), "a")

	def test_oldest_entry_is_evicted_beyond_max_size(self):
		first = self.cache.get(["mini.ctb"], backward=False)
		self.cache.get(["mini.ctb"], backward=True)
		self.cache.get(["include.ctb"], backward=False)
		self.assertEqual(len(self.cache), 2)
		self.assertIsNot(self.cache.get(["mini.ctb"], backward=False), first)

	def test_clear_drops_entries(self):
		first = self.cache.get(["mini.ctb"], backward=False)
		self.cache.clear()
		self.assertEqual(len(self.cache), 0)
		self.assertIsNot(self.cache.get(["mini.ctb"], backward=False), first)

	def test_failed_compile_is_raised_again_without_recompiling(self):
		for _ in range(2):
			with self.assertRaises(louis_py.TableParseError) as context:
				self.cache.get(["broken.ctb"], backward=False)
			self.assertTrue(context.exception.errors)
		self.assertEqual(self.compile.call_count, 1)

	def test_unresolvable_table_is_cached_as_failure(self):
		self.compile.side_effect = LookupError("no such table")
		for _ in range(2):
			with self.assertRaises(LookupError):
				self.cache.get(["missing.ctb"], backward=False)
		self.assertEqual(self.compile.call_count, 1)

	def test_clear_forgets_failures(self):
		with self.assertRaises(louis_py.TableParseError):
			self.cache.get(["broken.ctb"], backward=False)
		self.cache.clear()
		with self.assertRaises(louis_py.TableParseError):
			self.cache.get(["broken.ctb"], backward=False)
		self.assertEqual(self.compile.call_count, 2)

	def test_unexpected_error_propagates_and_is_not_cached(self):
		self.compile.side_effect = RuntimeError("boom")
		for _ in range(2):
			with self.assertRaises(RuntimeError):
				self.cache.get(["mini.ctb"], backward=False)
		self.assertEqual(self.compile.call_count, 2)

	def test_compile_is_logged_at_debug_only_on_a_miss(self):
		self.cache.get(["mini.ctb"], backward=False)
		self.assertEqual(len(log.recordsAt("debug")), 1)
		self.cache.get(["mini.ctb"], backward=False)
		self.assertEqual(len(log.recordsAt("debug")), 1)


class TestIsRecoverable(unittest.TestCase):
	def test_ordinary_exception_is_recoverable(self):
		self.assertTrue(translator.isRecoverable(ValueError("x")))

	def test_rust_panic_is_recoverable(self):
		self.assertTrue(translator.isRecoverable(PanicException("boom")))

	def test_keyboard_interrupt_is_not_recoverable(self):
		self.assertFalse(translator.isRecoverable(KeyboardInterrupt()))


@dataclass
class FakeResult:
	output: str
	input_positions: list[int]
	output_positions: list[int]
	cursor_pos: int | None


def fakeTranslator(result: FakeResult) -> mock.Mock:
	return mock.Mock(**{"translate_with_options.return_value": result})


class TestTranslateText(unittest.TestCase):
	def setUp(self):
		log.records.clear()
		self.mini = translator.compileTranslator([MINI], False, TABLES)

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
		fake = fakeTranslator(FakeResult("\u2801\u2803", [0], [0, 1], None))
		with self.assertRaises(translator.PositionError):
			translator.translateText(fake, "ab", mode=0, emphasis=[], cursorPos=None)

	def test_position_error_is_a_louis_error(self):
		self.assertTrue(issubclass(translator.PositionError, louis_py.LouisError))

	def test_non_braille_output_becomes_full_cells_and_is_logged(self):
		fake = fakeTranslator(FakeResult("\u2801x", [0, 1], [0, 1], None))
		cells, _, _, _ = translator.translateText(fake, "ab", mode=0, emphasis=[], cursorPos=None)
		self.assertEqual(cells, [1, 0xFF])
		self.assertEqual(len(log.recordsAt("debug")), 1)


class TestBackTranslateCells(unittest.TestCase):
	def setUp(self):
		self.mini = translator.compileTranslator([MINI], True, TABLES)

	def test_cells_are_back_translated(self):
		self.assertEqual(translator.backTranslateCells(self.mini, [1, 3], mode=0), "ab")

	def test_escaped_undefined_cells_are_dropped(self):
		self.assertEqual(translator.backTranslateCells(self.mini, [1, 0x3F, 3], mode=0), "ab")

	def test_cells_are_masked_to_a_byte(self):
		self.assertEqual(translator.backTranslateCells(self.mini, [0x101, 0x103], mode=0), "ab")

	def test_no_cells_give_empty_string(self):
		self.assertEqual(translator.backTranslateCells(self.mini, [], mode=0), "")
