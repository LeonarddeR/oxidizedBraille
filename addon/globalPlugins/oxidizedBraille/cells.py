# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Conversions between NVDA's braille cell integers and the Unicode braille louis-rs works with."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

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
) -> list[tuple[str, int, int]]:
	"""Run-length encode per-character typeform flags into ``(class, start, end)`` spans.

	The flags are padded with plain text or truncated to ``length``.
	Every class in ``classes`` yields its own spans, so combined flags produce overlapping spans.
	"""
	if typeform is None:
		return []
	flags = list(typeform[:length]) + [0] * (length - len(typeform))
	spans: list[tuple[str, int, int]] = []
	for bit, className in classes.items():
		start: int | None = None
		for index, flag in enumerate(flags):
			active = bool(flag & bit)
			if active and start is None:
				start = index
			elif not active and start is not None:
				spans.append((className, start, index))
				start = None
		if start is not None:
			spans.append((className, start, len(flags)))
	return spans
