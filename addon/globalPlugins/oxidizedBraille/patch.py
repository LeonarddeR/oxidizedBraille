# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Drop-in replacements for louisHelper.translate and louisHelper.backTranslate."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar

import louisHelper
from logHandler import log

from . import louis_py, translator
from .cells import mapFlags, typeformToEmphasis
from .translator import isRecoverable

T = TypeVar("T")

PATCHED_NAMES = ("translate", "backTranslate")

TableKey = tuple[tuple[str, ...], bool]
"""Table names as NVDA passes them, plus whether the direction is backward."""

CompileFunction = Callable[[tuple[str, ...], bool], louis_py.Translator]
"""Compiles a translator for table names as NVDA passes them and a direction."""

MODE_MAP: Mapping[int, int] = {
	louisHelper.TranslationMode.COMPBRL_AT_CURSOR: louis_py.TranslationMode.COMPBRL_AT_CURSOR,
	louisHelper.TranslationMode.PARTIAL_TRANS: louis_py.TranslationMode.PARTIAL_TRANS,
}
"""NVDA translation mode bits and the louis-rs mode bits they map to."""

TYPEFORM_CLASSES: Mapping[int, str] = {
	louisHelper.Typeform.ITALIC: "italic",
	louisHelper.Typeform.BOLD: "bold",
	louisHelper.Typeform.UNDERLINE: "underline",
}
"""NVDA typeform bits and the louis-rs emphasis classes they map to."""


class LouisHelperPatch:
	"""Runs translations through louis-rs, falling back to the original liblouis functions on failure."""

	def __init__(self, compile: CompileFunction):
		self._compile = compile
		self._translators: dict[TableKey, louis_py.Translator | Exception] = {}
		self._originals: dict[str, Callable[..., Any]] = {}
		self._reported: set[TableKey] = set()

	def _translator(self, key: TableKey) -> louis_py.Translator:
		"""Return the translator for ``key``, compiling it on first use.

		A failed compile is raised again on every later call until :meth:`clearCache`.
		"""
		entry = self._translators.get(key)
		if entry is None:
			try:
				entry = self._compile(*key)
			except (louis_py.LouisError, LookupError) as exc:
				entry = exc
			self._translators[key] = entry
		if isinstance(entry, Exception):
			raise entry.with_traceback(None)
		return entry

	def _run(
		self,
		tableList: Sequence[str],
		backward: bool,
		work: Callable[[louis_py.Translator], T],
		fallback: Callable[[], T],
	) -> T:
		key: TableKey = (tuple(tableList), backward)
		try:
			return work(self._translator(key))
		except BaseException as exc:
			if not isRecoverable(exc):
				raise
			self._report(key, exc)
			return fallback()

	def _report(self, key: TableKey, exc: BaseException) -> None:
		"""Log a failure once per table list and direction."""
		if key in self._reported:
			return
		self._reported.add(key)
		tables, backward = key
		direction = "backward" if backward else "forward"
		if isinstance(exc, louis_py.TableParseError | LookupError):
			details = getattr(exc, "errors", None)
			suffix = f": {'; '.join(details)}" if details else ""
			log.error(
				f"louis-rs cannot use tables {list(tables)} for {direction} translation; "
				f"falling back to liblouis for them until the next configuration reset. {exc}{suffix}",
			)
		else:
			log.exception(
				f"louis-rs {direction} translation with {list(tables)} failed; "
				"falling back to liblouis for this call",
			)

	def translate(
		self,
		tableList: list[str],
		inbuf: str,
		typeform: Sequence[int] | None = None,
		cursorPos: int | None = None,
		mode: int = 0,
	) -> tuple[list[int], list[int], list[int], int | None]:
		text = inbuf.replace("\0", "")
		return self._run(
			tableList,
			False,
			work=lambda compiled: translator.translateText(
				compiled,
				text,
				mode=mapFlags(mode, MODE_MAP),
				emphasis=typeformToEmphasis(typeform, TYPEFORM_CLASSES, len(text)),
				cursorPos=cursorPos,
			),
			fallback=lambda: self._originals["translate"](tableList, inbuf, typeform, cursorPos, mode),
		)

	def backTranslate(self, tableList: list[str], cells: list[int], mode: int = 0) -> str:
		return self._run(
			tableList,
			True,
			work=lambda compiled: translator.backTranslateCells(
				compiled,
				cells,
				mode=mapFlags(mode, MODE_MAP) | louis_py.TranslationMode.NO_UNDEFINED,
			),
			fallback=lambda: self._originals["backTranslate"](tableList, cells, mode),
		)

	def install(self, module: Any) -> None:
		"""Replace ``translate`` and ``backTranslate`` on the louisHelper module with this patch's methods."""
		if self._originals:
			raise RuntimeError("The patch is already installed")
		if any(
			isinstance(getattr(getattr(module, name), "__self__", None), LouisHelperPatch)
			for name in PATCHED_NAMES
		):
			raise RuntimeError("louisHelper is already patched by another instance")
		self._originals = {name: getattr(module, name) for name in PATCHED_NAMES}
		for name in PATCHED_NAMES:
			setattr(module, name, getattr(self, name))

	def uninstall(self, module: Any) -> None:
		"""Restore the functions captured by :meth:`install`, unless someone else replaced them since."""
		for name, original in self._originals.items():
			if getattr(getattr(module, name), "__self__", None) is self:
				setattr(module, name, original)
			else:
				log.warning(
					f"{name} was replaced by something else after this add-on patched it; leaving it alone",
				)
		self._originals = {}
		self.clearCache()

	def clearCache(self) -> None:
		self._translators.clear()
		self._reported.clear()
