# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Drop-in replacements for louisHelper.translate and louisHelper.backTranslate."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar

from logHandler import log

from . import louis_py, translator
from .cells import mapFlags, typeformToEmphasis
from .translator import TranslatorCache, isRecoverable

T = TypeVar("T")

BrokenKey = tuple[tuple[str, ...], bool]
"""Table names as NVDA passes them, plus whether the direction is backward."""


class LouisHelperPatch:
	"""Runs translations through louis-rs, falling back to the original liblouis functions on failure."""

	def __init__(
		self,
		*,
		cache: TranslatorCache,
		resolveTables: Callable[[list[str]], Sequence[str]],
		getSearchDirs: Callable[[Sequence[str]], Sequence[str]],
		modeMap: Mapping[int, int],
		typeformClasses: Mapping[int, str],
	):
		self._cache = cache
		self._resolveTables = resolveTables
		self._getSearchDirs = getSearchDirs
		self._modeMap = dict(modeMap)
		self._typeformClasses = dict(typeformClasses)
		self._original: tuple[Callable[..., Any], Callable[..., Any]] | None = None
		self._broken: dict[BrokenKey, str] = {}
		self._reported: set[BrokenKey] = set()

	def _run(
		self,
		tableList: Sequence[str],
		backward: bool,
		work: Callable[[louis_py.Translator], T],
		fallback: Callable[[], T],
	) -> T:
		key: BrokenKey = (tuple(tableList), backward)
		if key in self._broken:
			return fallback()
		try:
			tables = tuple(self._resolveTables(list(tableList)))
			compiled = self._cache.get(tables, self._getSearchDirs(tables), backward)
			return work(compiled)
		except BaseException as exc:
			if not isRecoverable(exc):
				raise
			self._handleFailure(key, exc)
			return fallback()

	def _handleFailure(self, key: BrokenKey, exc: BaseException) -> None:
		tables, backward = key
		direction = "backward" if backward else "forward"
		if isinstance(exc, louis_py.TableParseError | LookupError):
			self._broken[key] = str(exc)
			details = getattr(exc, "errors", None)
			suffix = f": {'; '.join(details)}" if details else ""
			log.error(
				f"louis-rs cannot use tables {list(tables)} for {direction} translation; "
				f"falling back to liblouis for them until the next configuration reset. {exc}{suffix}",
			)
			return
		if key in self._reported:
			log.debug(f"louis-rs {direction} translation with {list(tables)} failed again: {exc!r}")
			return
		self._reported.add(key)
		log.exception(
			f"louis-rs {direction} translation with {list(tables)} failed; "
			"falling back to liblouis for this call",
		)

	@property
	def _originalTranslate(self) -> Callable[..., Any]:
		if self._original is None:
			raise RuntimeError("The patch is not installed")
		return self._original[0]

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
				mode=mapFlags(mode, self._modeMap),
				emphasis=typeformToEmphasis(typeform, self._typeformClasses, len(text)),
				cursorPos=cursorPos,
			),
			fallback=lambda: self._originalTranslate(tableList, inbuf, typeform, cursorPos, mode),
		)

	def clearCache(self) -> None:
		self._cache.clear()
		self._broken.clear()
		self._reported.clear()
