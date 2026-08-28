# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Tests for the louisHelper replacement in ``patch``."""

from __future__ import annotations

import unittest
from typing import Any

from globalPlugins.oxidizedBraille import louis_py, patch
from logHandler import log

MODE_MAP = {
	2: int(louis_py.TranslationMode.COMPBRL_AT_CURSOR),
	256: int(louis_py.TranslationMode.PARTIAL_TRANS),
}
CLASSES = {1: "italic", 4: "bold", 2: "underline"}


class PanicException(BaseException):
	"""Stands in for pyo3_runtime.PanicException, matched by name."""


class FakeCache:
	"""Records requests; returns a sentinel translator or raises the configured error."""

	def __init__(self, error: BaseException | None = None):
		self.error = error
		self.calls: list[tuple[tuple[str, ...], tuple[str, ...], bool]] = []
		self.cleared = 0

	def get(self, tables: Any, searchDirs: Any, backward: bool) -> object:
		self.calls.append((tuple(tables), tuple(searchDirs), backward))
		if self.error is not None:
			raise self.error
		return "translator"

	def clear(self):
		self.cleared += 1


def makePatch(cache: FakeCache, resolveTables: Any = tuple) -> patch.LouisHelperPatch:
	return patch.LouisHelperPatch(
		cache=cache,
		resolveTables=resolveTables,
		getSearchDirs=lambda tables: ("dir-of-" + tables[0],),
		modeMap=MODE_MAP,
		typeformClasses=CLASSES,
	)


def work(translator: object) -> str:
	return f"louis-rs via {translator}"


def fallback() -> str:
	return "liblouis"


def raising(error: BaseException) -> Any:
	def work(translator: object) -> str:
		raise error

	return work


class TestFallback(unittest.TestCase):
	def setUp(self):
		log.records.clear()

	def test_success_uses_work_result(self):
		cache = FakeCache()
		self.assertEqual(makePatch(cache)._run(["a.ctb"], False, work, fallback), "louis-rs via translator")
		self.assertEqual(cache.calls, [(("a.ctb",), ("dir-of-a.ctb",), False)])

	def test_table_parse_error_falls_back_and_logs_once(self):
		cache = FakeCache(louis_py.TableParseError("bad table"))
		louisPatch = makePatch(cache)
		self.assertEqual(louisPatch._run(["a.ctb"], False, work, fallback), "liblouis")
		self.assertEqual(len(log.recordsAt("error")), 1)
		self.assertEqual(louisPatch._run(["a.ctb"], False, work, fallback), "liblouis")
		self.assertEqual(len(cache.calls), 1)
		self.assertEqual(len(log.records), 1)

	def test_broken_key_is_per_direction(self):
		cache = FakeCache(louis_py.TableParseError("bad table"))
		louisPatch = makePatch(cache)
		louisPatch._run(["a.ctb"], False, work, fallback)
		louisPatch._run(["a.ctb"], True, work, fallback)
		self.assertEqual(len(cache.calls), 2)

	def test_unresolvable_table_falls_back_and_logs_once(self):
		def resolveTables(tables: list[str]) -> tuple[str, ...]:
			raise LookupError("no such table")

		cache = FakeCache()
		louisPatch = makePatch(cache, resolveTables)
		self.assertEqual(louisPatch._run(["missing.ctb"], False, work, fallback), "liblouis")
		self.assertEqual(louisPatch._run(["missing.ctb"], False, work, fallback), "liblouis")
		self.assertEqual(cache.calls, [])
		self.assertEqual(len(log.recordsAt("error")), 1)

	def test_translation_error_falls_back_without_marking(self):
		cache = FakeCache()
		louisPatch = makePatch(cache)
		error = louis_py.TranslationError("boom")
		self.assertEqual(louisPatch._run(["a.ctb"], False, raising(error), fallback), "liblouis")
		self.assertEqual(louisPatch._run(["a.ctb"], False, raising(error), fallback), "liblouis")
		self.assertEqual(len(cache.calls), 2)
		self.assertEqual(len(log.recordsAt("exception")), 1)
		self.assertEqual(len(log.recordsAt("debug")), 1)

	def test_rust_panic_falls_back(self):
		louisPatch = makePatch(FakeCache())
		self.assertEqual(
			louisPatch._run(["a.ctb"], False, raising(PanicException("boom")), fallback),
			"liblouis",
		)

	def test_keyboard_interrupt_propagates(self):
		louisPatch = makePatch(FakeCache())
		with self.assertRaises(KeyboardInterrupt):
			louisPatch._run(["a.ctb"], False, raising(KeyboardInterrupt()), fallback)

	def test_clear_cache_re_enables_broken_key(self):
		cache = FakeCache(louis_py.TableParseError("bad table"))
		louisPatch = makePatch(cache)
		louisPatch._run(["a.ctb"], False, work, fallback)
		louisPatch.clearCache()
		louisPatch._run(["a.ctb"], False, work, fallback)
		self.assertEqual(len(cache.calls), 2)
		self.assertEqual(cache.cleared, 1)
