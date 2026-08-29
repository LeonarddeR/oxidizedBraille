# Oxidized Braille Translation

* Author: Leonard de Ruijter
* Download [latest release](https://github.com/LeonarddeR/oxidizedBraille/releases/latest)
* NVDA compatibility: 2026.3 and later

This experimental add-on makes NVDA translate braille with [louis-rs](https://github.com/liblouis/louis-rs), a re-implementation of the liblouis braille translator in Rust, through the [louis-py](https://github.com/LeonarddeR/louis-py) Python bindings.
It exists to test louis-rs with real braille tables and real usage.
Expect differences from liblouis; please report them with the braille table you used.

## What it does

NVDA translates text to braille and braille input back to text through two functions in its `louisHelper` module.
While this add-on is enabled, those two functions run louis-rs instead of liblouis.
Everything else stays as it is: the list of braille tables, the table language detection and NVDA's own log line about the liblouis version still come from liblouis, which remains loaded.

If louis-rs cannot compile the selected table, that table is served by liblouis until NVDA's configuration is reset or NVDA restarts.
One line in the NVDA log tells you when that happens.
If a single translation fails, that translation falls back to liblouis as well.

## Checking which engine is in use

After starting NVDA, the log (NVDA+F1) contains a line starting with "Oxidized Braille Translation" that names the louis-py version in use.
A line starting with "louis-rs cannot use tables" means the selected table is handled by liblouis.

From the NVDA Python console (NVDA+control+Z) you can compare both engines directly:

```python
import louisHelper
tables = ["en-ueb-g2.ctb", "braille-patterns.cti"]
louisHelper.translate(tables, "Hello world", cursorPos=3)
louisHelper.translate.__self__._originals["translate"](tables, "Hello world", cursorPos=3)
```

The first call uses louis-rs, the second the original liblouis function.

## Known gaps

The louis-rs revision in this release accepts, but does not yet apply, several liblouis translation modes.
As a result:

* "Expand the word at the cursor to computer braille" has no effect ([louis-rs#20](https://github.com/liblouis/louis-rs/issues/20)).
* Contracted braille input is translated as if every buffered word were complete, so intermediate words may read differently than with liblouis ([louis-rs#19](https://github.com/liblouis/louis-rs/issues/19)).
* Bold, italic and underline are not indicated in braille output.
* Characters a table does not define are shown as a short `\x` escape rather than liblouis's `\xHHHH` form. Cells typed on a braille display that the input table does not define are dropped.
* Routing and cursor positions may differ from liblouis in contracted tables.
* A table included by another table is looked up next to the tables selected for translation and among NVDA's built-in tables. This differs from liblouis only when a table includes another table from a third directory ([louis-rs#15](https://github.com/liblouis/louis-rs/issues/15) and [#16](https://github.com/liblouis/louis-rs/issues/16), fixed by [louis-rs#28](https://github.com/liblouis/louis-rs/pull/28) but not yet available through louis-py).

The add-on only works on 64-bit Windows.
Restart NVDA after updating the add-on.

## Third-party components

The add-on bundles louis-py, which contains louis-rs. Both are licensed under the GNU Lesser General Public License version 2.1 or later; the license text is shipped in the `louis_py` folder of the add-on together with a record of the exact versions bundled.

* louis-rs: <https://github.com/liblouis/louis-rs>
* louis-py: <https://github.com/LeonarddeR/louis-py>

The add-on itself is licensed under the GNU General Public License version 2 or later.

## Development

Building and testing follows the NVDA add-on template: `uv sync`, `uv run scons` to build the add-on, `uv run prek run --all-files` for linting, type checking and the unit tests.
Type checking with ty expects a built NVDA source checkout in a sibling `nvda` directory.

The `louis_py` package under `addon/globalPlugins/oxidizedBraille/louis_py` is copied from a louis-py wheel. To update it:

1. In a louis-py checkout next to this repository, run `uv run --with maturin maturin build --release`.
2. Run `uv run python scripts/vendorLouisPy.py ../louis-py/target/wheels/<wheel file>` here.

The script records the louis-py commit and louis-rs revision in `louis_py/VENDORED.txt`.
