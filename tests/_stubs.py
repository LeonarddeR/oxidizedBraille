# Oxidized Braille Translation: NVDA add-on
# Copyright 2026 Leonard de Ruijter <alderuijter@gmail.com>
# License: GNU General Public License version 2.0 or later

"""Stand-ins for NVDA runtime modules, installed into ``sys.modules``.

Only what ``globalPlugins.oxidizedBraille`` imports is stubbed: ``logHandler``,
``globalPluginHandler``, ``addonHandler``, ``louisHelper``, ``brailleTables`` and ``config``.
Table names resolve against ``tests/tables``.
"""

from __future__ import annotations

import enum
import inspect
import sys
import types
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest.mock import Mock

TABLES_DIR = Path(__file__).resolve().parent / "tables"


class PanicException(BaseException):
	"""Stands in for pyo3_runtime.PanicException, which the add-on recognises by name."""


class FakeLogger:
	"""Collects log records so tests can assert on them."""

	def __init__(self):
		self.records: list[tuple[str, str]] = []

	def _log(self, level: str, msg: Any):
		self.records.append((level, str(msg)))

	def debug(self, msg: Any, *args: Any, **kwargs: Any):
		self._log("debug", msg)

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
		"""Calls every handler with only the keyword arguments its signature accepts, like NVDA does."""
		for handler in list(self.handlers):
			parameters = inspect.signature(handler).parameters
			if any(parameter.kind == parameter.VAR_KEYWORD for parameter in parameters.values()):
				handler(**kwargs)
			else:
				handler(**{name: value for name, value in kwargs.items() if name in parameters})


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
	louisHelper.translate = Mock(return_value=([], [], [], None))
	louisHelper.backTranslate = Mock(return_value="")
	return louisHelper


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
		version = "0.0-test"

	addonHandler.getCodeAddon = lambda: Addon()

	config = _module("config")
	config.post_configReset = FakeAction()

	brailleTables = _module("brailleTables")
	brailleTables.TABLES_DIR = str(TABLES_DIR)

	_installLouisHelper()
