# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Conversions between NVDA's braille cell integers and the Unicode braille louis-rs works with."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from .louis_py import EmphasisSpan

UNICODE_BRAILLE_START = 0x2800
UNICODE_BRAILLE_END = 0x28FF
UNDEFINED_CELL = 0xFF
"""Cell substituted for output characters outside the Unicode braille block."""


def isUnicodeBraille(char: str) -> bool:
	return UNICODE_BRAILLE_START <= ord(char) <= UNICODE_BRAILLE_END


def unicodeToCells(braille: str) -> list[int]:
	"""Map every character to a cell, so the result is index-aligned with the input."""
	return [
		ord(char) - UNICODE_BRAILLE_START if isUnicodeBraille(char) else UNDEFINED_CELL for char in braille
	]


def cellsToUnicode(cells: Iterable[int]) -> str:
	return "".join(chr(UNICODE_BRAILLE_START + (cell & 0xFF)) for cell in cells)


def stripUnicodeBraille(text: str) -> str:
	return "".join(char for char in text if not isUnicodeBraille(char))


def mapFlags(value: int, mapping: Mapping[int, int]) -> int:
	"""Translate the bits of ``value`` through ``mapping``; bits without a mapping are dropped."""
	result = 0
	for sourceBit, targetBit in mapping.items():
		if value & sourceBit:
			result |= targetBit
	return result


def normalizeCursor(cursorPos: int | None, length: int) -> int | None:
	if cursorPos is None:
		return None
	return min(max(cursorPos, 0), length)


def typeformToEmphasis(
	typeform: Sequence[int] | None,
	classes: Mapping[int, str],
	length: int,
) -> list[EmphasisSpan]:
	"""Run-length encode per-character typeform flags into one span per uninterrupted run of a class.

	The flags are padded with plain text or truncated to ``length``.
	"""
	if typeform is None or not any(typeform):
		return []
	flags = [int(flag) for flag in typeform[:length]]
	# Padding to the length plus a closing zero, so every run ends inside the loop.
	flags.extend([0] * (length - len(flags) + 1))
	spans: list[EmphasisSpan] = []
	starts: dict[int, int | None] = dict.fromkeys(classes)
	for index, value in enumerate(flags):
		for bit, className in classes.items():
			start = starts[bit]
			if value & bit:
				if start is None:
					starts[bit] = index
			elif start is not None:
				spans.append(EmphasisSpan(className, start, index))
				starts[bit] = None
	return spans
