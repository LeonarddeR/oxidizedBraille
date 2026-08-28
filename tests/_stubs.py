# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Stand-ins for NVDA runtime modules, installed into ``sys.modules``.

Only what ``globalPlugins.oxidizedBraille`` imports is stubbed: ``logHandler``,
``globalPluginHandler``, ``addonHandler``, ``louisHelper``, ``brailleTables`` and ``config``.
Table names resolve against ``tests/tables``.
"""

from __future__ import annotations

import collections
import enum
import os
import sys
import types
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

TABLES_DIR = Path(__file__).resolve().parent / "tables"


class FakeLogger:
	"""Collects log records so tests can assert on them."""

	DEBUG = 10
	INFO = 20
	WARNING = 30
	ERROR = 40

	def __init__(self):
		self.records: list[tuple[str, str]] = []

	def isEnabledFor(self, level: int) -> bool:
		return True

	def _log(self, level: str, msg: Any):
		self.records.append((level, str(msg)))

	def debug(self, msg: Any, *args: Any, **kwargs: Any):
		self._log("debug", msg)

	def debugWarning(self, msg: Any, *args: Any, **kwargs: Any):
		self._log("debugWarning", msg)

	def info(self, msg: Any, *args: Any, **kwargs: Any):
		self._log("info", msg)

	def warning(self, msg: Any, *args: Any, **kwargs: Any):
		self._log("warning", msg)

	def error(self, msg: Any, *args: Any, **kwargs: Any):
		self._log("error", msg)

	def exception(self, msg: Any = "", *args: Any, **kwargs: Any):
		self._log("exception", msg)

	def recordsAt(self, level: str) -> list[str]:
		return [msg for lvl, msg in self.records if lvl == level]


class FakeAction:
	"""Mimics ``extensionPoints.Action``: tracks registered handlers."""

	def __init__(self):
		self.handlers: list[Callable[..., Any]] = []

	def register(self, handler: Callable[..., Any]):
		self.handlers.append(handler)

	def unregister(self, handler: Callable[..., Any]):
		self.handlers.remove(handler)

	def notify(self, **kwargs: Any):
		for handler in list(self.handlers):
			handler(**kwargs)


class SpyFunction:
	"""Callable that records its calls and returns a fixed value."""

	def __init__(self, returnValue: Any):
		self.returnValue = returnValue
		self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

	def __call__(self, *args: Any, **kwargs: Any) -> Any:
		self.calls.append((args, kwargs))
		return self.returnValue


def _module(name: str) -> types.ModuleType:
	module = types.ModuleType(name)
	sys.modules[name] = module
	return module


def _installLouisHelper() -> types.ModuleType:
	louisHelper = _module("louisHelper")

	class Typeform(enum.IntFlag):
		PLAIN_TEXT = 0
		ITALIC = 1
		UNDERLINE = 2
		BOLD = 4

	class TranslationMode(enum.IntFlag):
		NONE = 0
		COMPBRL_AT_CURSOR = 2
		PARTIAL_TRANS = 256

	def _resolveTableInner(tables: list[str], base: str | None = None) -> Generator[str]:
		for table in tables:
			path = TABLES_DIR / table
			if not path.is_file():
				raise LookupError(f"Could not resolve table {table!r}")
			yield str(path)

	louisHelper.Typeform = Typeform
	louisHelper.TranslationMode = TranslationMode
	louisHelper._resolveTableInner = _resolveTableInner
	louisHelper.translate = SpyFunction(([], [], [], None))
	louisHelper.backTranslate = SpyFunction("")
	return louisHelper


def _installBrailleTables() -> types.ModuleType:
	brailleTables = _module("brailleTables")

	class TableSource(enum.StrEnum):
		BUILTIN = "builtin"
		SCRATCHPAD = "scratchpad"

	brailleTables.TableSource = TableSource
	brailleTables.TABLES_DIR = str(TABLES_DIR)
	brailleTables._tablesDirs = collections.ChainMap({TableSource.BUILTIN: str(TABLES_DIR)}).new_child()
	return brailleTables


def install():
	"""Install all stub modules. Idempotent; must run before importing the plugin package."""
	if "louisHelper" in sys.modules:
		return

	logHandler = _module("logHandler")
	logHandler.log = FakeLogger()

	globalPluginHandler = _module("globalPluginHandler")

	class GlobalPlugin:
		def __init__(self, *args: Any, **kwargs: Any):
			pass

		def terminate(self, *args: Any, **kwargs: Any):
			pass

	globalPluginHandler.GlobalPlugin = GlobalPlugin

	addonHandler = _module("addonHandler")

	class Addon:
		name = "oxidizedBraille"
		version = "0.0-test"
		path = os.fspath(TABLES_DIR.parent.parent / "addon")

	addonHandler.Addon = Addon
	addonHandler.getCodeAddon = lambda: Addon()

	config = _module("config")
	config.conf = {"debugLog": {"louis": False}}
	config.post_configReset = FakeAction()

	_installLouisHelper()
	_installBrailleTables()
