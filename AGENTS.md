# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

## Project

Oxidized Braille Translation: experimental NVDA add-on that routes NVDA's braille translation through louis-rs (a Rust re-implementation of liblouis) via the louis-py bindings, by replacing `louisHelper.translate` and `louisHelper.backTranslate` at runtime. liblouis stays loaded as the fallback. Min NVDA 2026.3, Python 3.13, Windows x64 only.

Sibling source repos (paths relative to this repo):

* `..\nvda` — NVDA source, and it must be **built** (`scons source`), not merely cloned, for `ty` to resolve every NVDA import (`louisHelper`, `brailleTables`, `config`, …). CI gets a built tree from the `prepare-nvda-source` action. Look in the NVDA source for any API signature before guessing.
* `..\louis-py` — source of the louis-py wheel the add-on bundles (see below).

## Build / Lint / Test

Toolchain: `uv` + SCons. Run from repo root.

| Task | Command |
|---|---|
| Install dev deps | `uv sync` |
| Copy `louis_py` into the add-on (after every `uv sync`) | `uv run python scripts/copyLouisPy.py` |
| Build add-on (`.nvda-addon`) | `uv run scons` |
| Translation template | `uv run scons pot` |
| Lint + format + type check + tests | `uv run prek run --all-files` |
| Type check only | `uv run ty check` |
| Unit tests only | `uv run python -m unittest discover -s tests -t . -v` |
| Clean | `uv run scons -c` |

Git hooks run via **prek** (`prek.toml`); `uv run prek install -f` wires them. The hooks autofix formatting, so run `uv run prek run --files <files>` before staging to avoid a rejected commit. Commits on `main` are refused; work on a branch.

Type checking uses **ty** (`[tool.ty]` in `pyproject.toml`), scoped to `addon/` + `buildVars.py`, with the vendored `louis_py` excluded. Indentation is **tabs** (ruff `indent-style=tab`, `W191` ignored). Line length 110.

Tests are `unittest`; `tests/__init__.py` puts `addon/` on `sys.path` and `tests/_stubs.py` installs stand-ins for the NVDA modules the plugin imports, so no NVDA checkout is needed to run them. Every production change starts with a failing test.

## Layout

Everything lives in one package, `addon/globalPlugins/oxidizedBraille/`:

* `__init__.py` — `GlobalPlugin`: installs a `LouisHelperPatch` on `louisHelper`, registers its `clearCache` with `config.post_configReset` and restores the originals on `terminate`.
* `cells.py` — pure conversions: Unicode braille ↔ cell integers, mode bit mapping, typeform flags → `EmphasisSpan`s.
* `translator.py` — `compileTranslator` (passes each table's directory plus NVDA's built-in table directory to louis-py as `search_path=`), `translateText`, `backTranslateCells`.
* `patch.py` — `compileTables` (NVDA's `louisHelper._resolveTableInner` plus `brailleTables.TABLES_DIR`), `isRecoverable`, and `LouisHelperPatch`: the replacement `translate`/`backTranslate` with the NVDA→louis-rs mode and typeform maps, translators kept per table list and direction (a failed compile is logged once and kept as a failure), fallback to liblouis, `install`/`uninstall`.
* `louis_py/` — copied from the installed louis-py wheel by `scripts/copyLouisPy.py`; gitignored, never edit.

## louis-rs constraints the code works around

At the vendored revision louis-rs looks tables and `include` lines up only in the directories louis-py is handed as `search_path=`, does not apply translation modes (#19 `partialTrans`, #20 `compbrlAtCursor`), and renders undefined cells in back-translation as braille-character escapes (no issue filed). See the readme's "Known gaps" before changing behaviour here. Honouring `NO_UNDEFINED` retires the braille stripping in `backTranslateCells`.

## Bundling louis_py

The louis-py `win_amd64` wheel is committed in `wheels/`, and `[tool.uv.sources]` in `pyproject.toml` points the `addon` dependency group at it. `uv sync` installs it; `scripts/copyLouisPy.py` copies the installed `louis_py` package and its LGPL `LICENSE` into the add-on. To update, replace the wheel (for example with the `wheels-windows-latest-x64` artifact of a louis-py CI run), update the `louis-py==` pin and the source path to match it, then run `uv lock`, `uv sync` and the copy script. Once louis-py is on PyPI, drop the source entry.

## buildVars / manifest

`buildVars.py` is the single source of truth for add-on metadata. `pythonSources` is a single-level glob on purpose: it must not reach into `louis_py/`, or gettext is pointed at vendored code. Bump `addon_version` and `addon_lastTestedNVDAVersion` there.
