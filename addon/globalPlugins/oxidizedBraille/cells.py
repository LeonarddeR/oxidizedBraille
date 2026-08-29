# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Conversions between NVDA's braille cell integers and the Unicode braille louis-rs works with."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from itertools import groupby

from .louis_py import EmphasisSpan

UNICODE_BRAILLE_START = 0x2800
UNICODE_BRAILLE_END = 0x28FF
UNDEFINED_CELL = 0xFF
"""Cell substituted for output characters outside the Unicode braille block."""


def isUnicodeBraille(char: str) -> bool:
	"""Whether a character is in the Unicode braille block.

	:param char: A single character.
	"""
	return UNICODE_BRAILLE_START <= ord(char) <= UNICODE_BRAILLE_END


def unicodeToCells(braille: str) -> list[int]:
	"""Map every character to a cell, so the result is index-aligned with the input.

	:param braille: Text as louis-rs outputs it, normally Unicode braille.
	:return: One cell per character; a character outside the braille block
		becomes :data:`UNDEFINED_CELL`.
	"""
	return [
		ord(char) - UNICODE_BRAILLE_START if isUnicodeBraille(char) else UNDEFINED_CELL for char in braille
	]


def cellsToUnicode(cells: Iterable[int]) -> str:
	"""Convert cells to Unicode braille.

	:param cells: Braille cells; every cell is masked to a byte.
	:return: One braille character per cell.
	"""
	return "".join(chr(UNICODE_BRAILLE_START + (cell & 0xFF)) for cell in cells)


def stripUnicodeBraille(text: str) -> str:
	"""Remove every Unicode braille character from text.

	In back-translated text, braille characters only occur in the escape louis-rs writes for a cell
	the table does not define (``\\x283f`` spelled in cells). Dead code once louis-rs honours
	``NO_UNDEFINED``; there is no louis-rs issue for that yet.

	:param text: Text as louis-rs outputs it.
	:return: ``text`` without its braille characters.
	"""
	return "".join(char for char in text if not isUnicodeBraille(char))


def mapFlags(value: int, mapping: Mapping[int, int]) -> int:
	"""Translate the bits of ``value`` through ``mapping``; bits without a mapping are dropped.

	:param value: Bit flags to translate.
	:param mapping: Source bits to the target bits they stand for.
	:return: The target bits of every source bit set in ``value``.
	"""
	result = 0
	for sourceBit, targetBit in mapping.items():
		if value & sourceBit:
			result |= targetBit
	return result


def typeformToEmphasis(
	typeform: Sequence[int] | None,
	classes: Mapping[int, str],
	length: int,
) -> list[EmphasisSpan]:
	"""Convert NVDA's per-character typeform flags into the emphasis spans louis-rs takes.

	NVDA describes formatting as one flag value per character, with a bit per kind of
	formatting: ``[ITALIC, ITALIC | BOLD, ITALIC]`` means all three characters are italic and
	the second one is also bold. louis-rs wants one span per stretch of characters sharing a
	formatting class, as the class name plus start and end offsets, end exclusive. The example
	becomes ``[("italic", 0, 3), ("bold", 1, 2)]``.

	Every bit in ``classes`` is handled on its own: the flags are masked to that bit and cut into
	runs of equal value, and every run with the bit set becomes a span, so a run of one class is
	not cut by other bits coming and going inside it.

	:param typeform: One flag value per character, or ``None`` for no formatting. Missing values
		count as plain text, surplus values are ignored.
	:param classes: Typeform bits and the louis-rs class name each one stands for.
	:param length: The number of characters in the text; no span reaches past it.
	:return: The emphasis spans, grouped by class in the order of ``classes``, then by position.
	"""
	if typeform is None or not any(typeform):
		return []
	flags = [int(flag) for flag in typeform[:length]]
	flags.extend([0] * (length - len(flags)))
	spans: list[EmphasisSpan] = []
	for bit, className in classes.items():
		start = 0
		for isSet, run in groupby(flag & bit for flag in flags):
			end = start + len(list(run))
			if isSet:
				spans.append(EmphasisSpan(className, start, end))
			start = end
	return spans
