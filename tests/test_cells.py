# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Tests for the pure conversion helpers in ``cells``."""

from __future__ import annotations

import unittest

import louisHelper
from globalPlugins.oxidizedBraille import cells

CLASSES = {1: "italic", 4: "bold", 2: "underline"}


class TestUnicodeToCells(unittest.TestCase):
	def test_braille_characters_become_dot_masks(self):
		self.assertEqual(cells.unicodeToCells("⠁⠃⠉"), [1, 3, 9])

	def test_non_braille_character_becomes_undefined_cell(self):
		self.assertEqual(cells.unicodeToCells("⠁x"), [1, cells.UNDEFINED_CELL])


class TestCellsToUnicode(unittest.TestCase):
	def test_cells_become_braille_characters(self):
		self.assertEqual(cells.cellsToUnicode([1, 3]), "⠁⠃")


class TestStripUnicodeBraille(unittest.TestCase):
	def test_braille_characters_are_removed(self):
		self.assertEqual(cells.stripUnicodeBraille("a⠳⠭b"), "ab")

	def test_plain_text_is_unchanged(self):
		self.assertEqual(cells.stripUnicodeBraille("plain text"), "plain text")


class TestMapFlags(unittest.TestCase):
	MAPPING = {2: 1 << 1, 256: 1 << 6}

	def test_known_bits_are_mapped(self):
		self.assertEqual(cells.mapFlags(2 | 256, self.MAPPING), (1 << 1) | (1 << 6))

	def test_unknown_bits_are_dropped(self):
		self.assertEqual(cells.mapFlags(4, self.MAPPING), 0)

	def test_zero_maps_to_zero(self):
		self.assertEqual(cells.mapFlags(0, self.MAPPING), 0)


class TestTypeformToEmphasis(unittest.TestCase):
	def test_none_gives_no_spans(self):
		self.assertEqual(cells.typeformToEmphasis(None, CLASSES, 3), [])

	def test_all_plain_gives_no_spans(self):
		self.assertEqual(cells.typeformToEmphasis([0, 0, 0], CLASSES, 3), [])

	def test_single_run_gives_one_half_open_span(self):
		self.assertEqual(cells.typeformToEmphasis([0, 1, 1, 0], CLASSES, 4), [("italic", 1, 3)])

	def test_adjacent_runs_of_different_classes(self):
		self.assertEqual(
			cells.typeformToEmphasis([1, 1, 4, 4], CLASSES, 4),
			[("italic", 0, 2), ("bold", 2, 4)],
		)

	def test_combined_flags_give_one_span_per_class(self):
		self.assertEqual(
			cells.typeformToEmphasis([5, 5], CLASSES, 2),
			[("italic", 0, 2), ("bold", 0, 2)],
		)

	def test_class_run_continues_across_a_change_of_other_flags(self):
		self.assertEqual(
			cells.typeformToEmphasis([1, 5, 1], CLASSES, 3),
			[("bold", 1, 2), ("italic", 0, 3)],
		)

	def test_shorter_typeform_is_padded_with_plain(self):
		self.assertEqual(cells.typeformToEmphasis([1], CLASSES, 3), [("italic", 0, 1)])

	def test_longer_typeform_is_truncated_to_length(self):
		self.assertEqual(cells.typeformToEmphasis([1, 1, 1, 1], CLASSES, 2), [("italic", 0, 2)])

	def test_int_flag_members_are_accepted(self):
		typeform = [louisHelper.Typeform.ITALIC, louisHelper.Typeform.PLAIN_TEXT]
		self.assertEqual(cells.typeformToEmphasis(typeform, CLASSES, 2), [("italic", 0, 1)])

	def test_spans_are_emphasis_spans(self):
		(span,) = cells.typeformToEmphasis([1], CLASSES, 1)
		self.assertEqual((span.class_, span.start, span.end), ("italic", 0, 1))
