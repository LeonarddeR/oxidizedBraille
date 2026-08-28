# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Locates braille tables for louis-rs and caches compiled translators."""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from logHandler import log

from . import louis_py
from .cells import isUnicodeBraille, normalizeCursor, unicodeToCells

TABLE_PATH_VARIABLE = "LOUIS_TABLE_PATH"
"""Environment variable louis-rs reads to locate tables and their includes."""

TranslatorKey = tuple[tuple[str, ...], tuple[str, ...], bool]


def buildSearchDirs(
	tables: Sequence[str],
	customDirs: Sequence[str],
	builtinDir: str,
) -> tuple[str, ...]:
	"""Directories to search for includes: next to each table, then custom dirs, then the built-in dir."""
	dirs: dict[str, None] = {}
	for table in tables:
		dirs.setdefault(os.path.dirname(table), None)
	for directory in customDirs:
		dirs.setdefault(directory, None)
	dirs.setdefault(builtinDir, None)
	return tuple(dirs)


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


class TranslatorCache:
	"""Least-recently-used cache of compiled translators, keyed by tables, search dirs and direction."""

	def __init__(self, maxSize: int = 8):
		self._maxSize = maxSize
		self._entries: OrderedDict[TranslatorKey, louis_py.Translator] = OrderedDict()
		self._lock = threading.Lock()

	def __len__(self) -> int:
		return len(self._entries)

	def get(self, tables: Sequence[str], searchDirs: Sequence[str], backward: bool) -> louis_py.Translator:
		key: TranslatorKey = (tuple(tables), tuple(searchDirs), backward)
		with self._lock:
			cached = self._entries.get(key)
			if cached is not None:
				self._entries.move_to_end(key)
				return cached
			direction = louis_py.Direction.BACKWARD if backward else louis_py.Direction.FORWARD
			started = time.perf_counter()
			with tablePath(searchDirs):
				compiled = louis_py.Translator(list(tables), direction)
			self._entries[key] = compiled
			while len(self._entries) > self._maxSize:
				self._entries.popitem(last=False)
			log.debug(
				f"Compiled {'backward' if backward else 'forward'} translator for {tables} "
				f"in {time.perf_counter() - started:.3f} s",
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
	emphasis: Sequence[tuple[str, int, int]],
	cursorPos: int | None,
) -> tuple[list[int], list[int], list[int], int | None]:
	"""Translate ``text`` and shape the result like ``louisHelper.translate`` does."""
	result = compiled.translate_with_options(
		text,
		mode=mode,
		emphasis=list(emphasis) or None,
		cursor_pos=normalizeCursor(cursorPos, len(text)),
	)
	output = result.output
	cells = unicodeToCells(output)
	nonBraille = [f"U+{ord(char):04X}" for char in output if not isUnicodeBraille(char)]
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
	if cursorPos is None:
		brailleCursorPos = None
	elif result.cursor_pos is None:
		brailleCursorPos = min(max(cursorPos, 0), len(cells))
	else:
		brailleCursorPos = result.cursor_pos
	return cells, brailleToRawPos, rawToBraillePos, brailleCursorPos
