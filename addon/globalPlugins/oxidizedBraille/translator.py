# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Compiles louis-rs translators for NVDA's tables, caches them and shapes their results."""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator, Sequence
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

TableKey = tuple[tuple[str, ...], bool]
"""Table names as NVDA passes them, plus whether the direction is backward."""

CompileFunction = Callable[[Sequence[str], bool], louis_py.Translator]


def buildSearchDirs(tables: Sequence[str], builtinDir: str) -> tuple[str, ...]:
	"""Directories louis-rs may find includes in: next to each table, then the built-in table directory."""
	return tuple(dict.fromkeys([*(os.path.dirname(table) for table in tables), builtinDir]))


@contextmanager
def tablePath(dirs: Sequence[str]) -> Iterator[None]:
	"""Point louis-rs at ``dirs`` while the block runs, then restore the previous value."""
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
	"""Compile absolute table paths, resolving their includes the way NVDA's own resolver does."""
	direction = louis_py.Direction.BACKWARD if backward else louis_py.Direction.FORWARD
	with tablePath(buildSearchDirs(tables, builtinDir)):
		return louis_py.Translator(list(tables), direction)


class TranslatorCache:
	"""Least-recently-used cache of translators by table names and direction.

	A table list that failed to compile stays failed until :meth:`clear`; asking for it again
	raises the failure without compiling again.
	"""

	def __init__(self, compile: CompileFunction, maxSize: int = 8):
		self._compile = compile
		self._maxSize = maxSize
		self._entries: OrderedDict[TableKey, louis_py.Translator | Exception] = OrderedDict()
		self._lock = threading.Lock()

	def __len__(self) -> int:
		return len(self._entries)

	def get(self, tableList: Sequence[str], backward: bool) -> louis_py.Translator:
		key: TableKey = (tuple(tableList), backward)
		with self._lock:
			entry = self._entries.get(key)
			if entry is None:
				entry = self._compileEntry(tableList, backward)
				self._entries[key] = entry
				while len(self._entries) > self._maxSize:
					self._entries.popitem(last=False)
			else:
				self._entries.move_to_end(key)
		if isinstance(entry, Exception):
			raise entry.with_traceback(None)
		return entry

	def _compileEntry(self, tableList: Sequence[str], backward: bool) -> louis_py.Translator | Exception:
		started = time.perf_counter()
		try:
			compiled = self._compile(tableList, backward)
		except (louis_py.LouisError, LookupError) as exc:
			return exc
		direction = "backward" if backward else "forward"
		log.debug(
			f"Compiled {direction} translator for {list(tableList)} in {time.perf_counter() - started:.3f} s",
		)
		return compiled

	def clear(self) -> None:
		with self._lock:
			self._entries.clear()


def isRecoverable(exc: BaseException) -> bool:
	"""Whether a failure inside louis-rs may be handled by falling back to liblouis.

	Rust panics reach Python as ``pyo3_runtime.PanicException``, a ``BaseException`` subclass.
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
	"""Translate ``text`` and shape the result like ``louisHelper.translate`` does."""
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
	"""
	return stripUnicodeBraille(compiled.translate_with_options(cellsToUnicode(cells), mode=mode).output)
