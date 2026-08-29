# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Compiles louis-rs translators for NVDA's tables and shapes their results."""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from logHandler import log

from . import louis_py
from .cells import (
	UNDEFINED_CELL,
	cellsToUnicode,
	isUnicodeBraille,
	normalizeCursor,
	stripUnicodeBraille,
	unicodeToCells,
)

TABLE_PATH_VARIABLE = "LOUIS_TABLE_PATH"
"""Environment variable louis-rs reads to locate tables and their includes."""


def buildSearchDirs(tables: Sequence[str], builtinDir: str) -> tuple[str, ...]:
	"""Directories louis-rs may find includes in: next to each table, then the built-in table directory.

	:param tables: Absolute paths of the tables to compile.
	:param builtinDir: NVDA's built-in table directory.
	:return: The directories without duplicates, in lookup order.
	"""
	return tuple(dict.fromkeys([*(os.path.dirname(table) for table in tables), builtinDir]))


@contextmanager
def tablePath(dirs: Sequence[str]) -> Iterator[None]:
	"""Point louis-rs at ``dirs`` while the block runs, then restore the previous value.

	:param dirs: The directories to set :data:`TABLE_PATH_VARIABLE` to.
	:raises ValueError: If ``dirs`` is empty.
	"""
	if not dirs:
		raise ValueError("At least one directory is required; louis-rs finds nothing on an empty path")
	previous = os.environ.get(TABLE_PATH_VARIABLE)
	os.environ[TABLE_PATH_VARIABLE] = os.pathsep.join(dirs)
	try:
		yield
	finally:
		if previous is None:
			os.environ.pop(TABLE_PATH_VARIABLE, None)
		else:
			os.environ[TABLE_PATH_VARIABLE] = previous


def compileTranslator(tables: Sequence[str], backward: bool, builtinDir: str) -> louis_py.Translator:
	"""Compile absolute table paths, resolving their includes the way NVDA's own resolver does.

	:param tables: Absolute paths of the tables to compile.
	:param backward: Whether the translator back-translates braille to text.
	:param builtinDir: NVDA's built-in table directory.
	:return: The compiled translator.
	:raises louis_py.TableParseError: If louis-rs cannot compile the tables.
	"""
	direction = louis_py.Direction.BACKWARD if backward else louis_py.Direction.FORWARD
	with tablePath(buildSearchDirs(tables, builtinDir)):
		return louis_py.Translator(list(tables), direction)


def isRecoverable(exc: BaseException) -> bool:
	"""Whether a failure inside louis-rs may be handled by falling back to liblouis.

	Rust panics reach Python as ``pyo3_runtime.PanicException``, a ``BaseException`` subclass.

	:param exc: The exception raised while compiling or translating.
	"""
	return isinstance(exc, Exception) or type(exc).__name__ == "PanicException"


class PositionError(louis_py.LouisError):
	"""louis-rs returned position lists that do not match the text or the output."""


def translateText(
	compiled: louis_py.Translator,
	text: str,
	*,
	mode: int,
	emphasis: Sequence[louis_py.EmphasisSpan],
	cursorPos: int | None,
) -> tuple[list[int], list[int], list[int], int | None]:
	"""Translate ``text`` and shape the result like ``louisHelper.translate`` does.

	:param compiled: A forward translator.
	:param text: The text to translate.
	:param mode: louis-rs translation mode bits.
	:param emphasis: Emphasis spans for the formatted parts of ``text``.
	:param cursorPos: The cursor position in ``text``, or ``None`` for no cursor.
		A position outside the text is clamped to it.
	:return: The cells, the input position of every cell, the cell position of every character,
		and the cursor position in the cells, which is ``None`` when ``cursorPos`` is ``None``.
	:raises PositionError: If the position lists louis-rs returned do not match the text or the cells.
	"""
	result = compiled.translate_with_options(
		text,
		mode=mode,
		emphasis=list(emphasis) or None,
		cursor_pos=normalizeCursor(cursorPos, len(text)),
	)
	cells = unicodeToCells(result.output)
	if UNDEFINED_CELL in cells:
		nonBraille = [f"U+{ord(char):04X}" for char in result.output if not isUnicodeBraille(char)]
		if nonBraille:
			log.debug(
				f"louis-rs produced characters outside the braille block, shown as full cells: {nonBraille}",
			)
	brailleToRawPos = list(result.input_positions or [])
	rawToBraillePos = list(result.output_positions or [])
	if len(brailleToRawPos) != len(cells) or len(rawToBraillePos) != len(text):
		raise PositionError(
			f"Position lists do not match: {len(brailleToRawPos)} entries for {len(cells)} cells, "
			f"{len(rawToBraillePos)} entries for {len(text)} characters",
		)
	return cells, brailleToRawPos, rawToBraillePos, result.cursor_pos


def backTranslateCells(compiled: louis_py.Translator, cells: Sequence[int], *, mode: int) -> str:
	"""Back-translate cells the way ``louisHelper.backTranslate`` does, dropping undefined cells.

	louis-rs renders a cell it cannot back-translate as an escape made of braille characters,
	so removing braille characters from the output leaves only the translated text.

	:param compiled: A backward translator.
	:param cells: The braille cells to back-translate; every cell is masked to a byte.
	:param mode: louis-rs translation mode bits.
	:return: The back-translated text.
	"""
	return stripUnicodeBraille(compiled.translate_with_options(cellsToUnicode(cells), mode=mode).output)
