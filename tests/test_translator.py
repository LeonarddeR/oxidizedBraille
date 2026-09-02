# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Tests for table lookup and result shaping in ``translator``."""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from globalPlugins.oxidizedBraille import louis_py, translator
from logHandler import log

from tests._stubs import TABLES_DIR

TABLES = str(TABLES_DIR)
MINI = str(TABLES_DIR / "mini.ctb")
INCLUDE = str(TABLES_DIR / "include.ctb")
BROKEN = str(TABLES_DIR / "broken.ctb")
BOGUS_DIR = "C:/does-not-exist"


class TestCompileTranslator(unittest.TestCase):
	def test_environment_is_left_alone_while_compiling(self):
		seen: list[str | None] = []
		realTranslator = louis_py.Translator

		def recordingTranslator(*args, **kwargs):
			seen.append(os.environ.get("LOUIS_TABLE_PATH"))
			return realTranslator(*args, **kwargs)

		with (
			mock.patch.dict(os.environ, {"LOUIS_TABLE_PATH": "C:/ambient"}),
			mock.patch.object(translator.louis_py, "Translator", recordingTranslator),
		):
			translator.compileTranslator([MINI], False, BOGUS_DIR)
		self.assertEqual(seen, ["C:/ambient"])

	def test_ambient_table_path_variable_is_not_searched(self):
		with tempfile.TemporaryDirectory() as directory:
			table = Path(directory) / "custom.ctb"
			table.write_text("include mini.ctb\n", encoding="utf-8")
			with (
				mock.patch.dict(os.environ, {"LOUIS_TABLE_PATH": TABLES}),
				self.assertRaises(louis_py.TableParseError),
			):
				translator.compileTranslator([str(table)], False, BOGUS_DIR)

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

	def test_no_undefined_is_added_to_the_mode(self):
		fake = fakeTranslator(FakeResult("a", [], [], None))
		translator.backTranslateCells(fake, [1], mode=louis_py.TranslationMode.PARTIAL_TRANS)
		self.assertEqual(
			fake.translate_with_options.call_args.kwargs["mode"],
			louis_py.TranslationMode.PARTIAL_TRANS | louis_py.TranslationMode.NO_UNDEFINED,
		)
