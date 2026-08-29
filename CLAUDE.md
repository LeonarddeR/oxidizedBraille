# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Oxidized Braille Translation: experimental NVDA add-on that routes NVDA's braille translation through louis-rs (a Rust re-implementation of liblouis) via the louis-py bindings, by replacing `louisHelper.translate` and `louisHelper.backTranslate` at runtime. liblouis stays loaded as the fallback. Min NVDA 2026.3, Python 3.13, Windows x64 only.

Sibling source repos (paths relative to this repo):

* `..\nvda` — NVDA source, and it must be **built** (`scons source`), not merely cloned, for `ty` to resolve every NVDA import (`louisHelper`, `brailleTables`, `config`, …). CI gets a built tree from the `prepare-nvda-source` action. Look in the NVDA source for any API signature before guessing.
* `..\louis-py` — source of the vendored `louis_py` package (see below).

## Build / Lint / Test

Toolchain: `uv` + SCons. Run from repo root.

| Task | Command |
|---|---|
| Install dev deps | `uv sync` |
| Build add-on (`.nvda-addon`) | `uv run scons` |
| Translation template | `uv run scons pot` |
| Lint + format + type check + tests | `uv run prek run --all-files` |
| Type check only | `uv run ty check` |
| Unit tests only | `uv run python -m unittest discover -s tests -t . -v` |
| Clean | `uv run scons -c` |

Git hooks run via **prek** (`prek.toml`); `uv run prek install -f` wires them. The hooks autofix formatting, so run `uv run prek run --files <files>` before staging to avoid a rejected commit; the vendored `louis_py` is excluded from all hooks globally. Commits on `main` are refused; work on a branch.

Type checking uses **ty** (`[tool.ty]` in `pyproject.toml`), scoped to `addon/` + `buildVars.py`, with the vendored `louis_py` excluded. Indentation is **tabs** (ruff `indent-style=tab`, `W191` ignored). Line length 110.

Tests are `unittest`; `tests/__init__.py` puts `addon/` on `sys.path` and `tests/_stubs.py` installs stand-ins for the NVDA modules the plugin imports, so no NVDA checkout is needed to run them. Every production change starts with a failing test.

## Layout

Everything lives in one package, `addon/globalPlugins/oxidizedBraille/`:

* `__init__.py` — `GlobalPlugin`: wraps `_compile` (NVDA's `louisHelper._resolveTableInner` plus `brailleTables.TABLES_DIR`) in a `LouisHelperPatch`, installs that on `louisHelper` and restores the originals on `terminate`; a config reset clears the patch's translators.
* `cells.py` — pure conversions: Unicode braille ↔ cell integers, mode bit mapping, cursor clamping, typeform flags → `EmphasisSpan`s.
* `translator.py` — `LOUIS_TABLE_PATH` handling (`buildSearchDirs`, `tablePath`, `compileTranslator`), `translateText`, `backTranslateCells`, `isRecoverable`.
* `patch.py` — `LouisHelperPatch`: the replacement `translate`/`backTranslate` with the NVDA→louis-rs mode and typeform maps, translators kept per table list and direction (a failed compile is kept as a failure), fallback to liblouis logged once per table list, `install`/`uninstall`.
* `louis_py/` — vendored from a louis-py wheel; never edit. `VENDORED.txt` records the louis-py commit and louis-rs revision.

## louis-rs constraints the code works around

At the vendored revision louis-rs finds tables and `include` lines only through the `LOUIS_TABLE_PATH` environment variable (an empty value finds nothing, absolute paths work when it is set), does not apply translation modes or emphasis, and renders undefined cells in back-translation as braille-character escapes. See the readme's "Known gaps" before changing behaviour here; the proper fix for table lookup is a resolver API in louis-py.

## Vendoring louis_py

1. In `..\louis-py`: `uv run --with maturin maturin build --release` (maturin is only the build backend there). Check the wheel lists `louis_py/_louis_py.pyd`; an editable wheel only has a `.pth`.
2. Here: `uv run python scripts/vendorLouisPy.py ..\louis-py\target\wheels\<wheel>`.

## buildVars / manifest

`buildVars.py` is the single source of truth for add-on metadata. `pythonSources` is a single-level glob on purpose: it must not reach into `louis_py/`, or gettext is pointed at vendored code. Bump `addon_version` and `addon_lastTestedNVDAVersion` there.
