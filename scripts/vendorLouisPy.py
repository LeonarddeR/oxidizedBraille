"""Copy the louis_py package out of a louis-py wheel into the add-on.

Usage: uv run python scripts/vendorLouisPy.py <path to louis_py-*-win_amd64.whl>
"""

from __future__ import annotations

import datetime
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "addon" / "globalPlugins" / "oxidizedBraille" / "louis_py"
LOUIS_PY_REPO = REPO_ROOT.parent / "louis-py"
SKIPPED_SUFFIXES = (".pdb", ".pyc")


def louisRsRevision() -> str:
	cargoToml = (LOUIS_PY_REPO / "Cargo.toml").read_text(encoding="utf-8")
	match = re.search(r'louis-rs\s*=\s*\{[^}]*rev\s*=\s*"([0-9a-f]+)"', cargoToml)
	return match.group(1) if match else "unknown"


def louisPyCommit() -> str:
	result = subprocess.run(
		["git", "-C", str(LOUIS_PY_REPO), "rev-parse", "HEAD"],
		capture_output=True,
		text=True,
		check=False,
	)
	return result.stdout.strip() or "unknown"


def vendor(wheelPath: Path) -> None:
	with zipfile.ZipFile(wheelPath) as wheel:
		names = wheel.namelist()
		if "louis_py/_louis_py.pyd" not in names:
			sys.exit(f"{wheelPath} does not contain louis_py/_louis_py.pyd; is it an editable wheel?")
		shutil.rmtree(TARGET, ignore_errors=True)
		TARGET.mkdir(parents=True)
		for name in names:
			if not name.startswith("louis_py/") or name.endswith(SKIPPED_SUFFIXES) or "__pycache__" in name:
				continue
			destination = TARGET / name.removeprefix("louis_py/")
			destination.parent.mkdir(parents=True, exist_ok=True)
			destination.write_bytes(wheel.read(name))
		licenseNames = [n for n in names if n.endswith(".dist-info/licenses/LICENSE")]
		if licenseNames:
			(TARGET / "LICENSE").write_bytes(wheel.read(licenseNames[0]))
		else:
			shutil.copyfile(LOUIS_PY_REPO / "LICENSE", TARGET / "LICENSE")
	(TARGET / "VENDORED.txt").write_text(
		f"wheel: {wheelPath.name}\n"
		f"louis-py commit: {louisPyCommit()}\n"
		f"louis-rs revision: {louisRsRevision()}\n"
		f"vendored on: {datetime.date.today().isoformat()}\n",
		encoding="utf-8",
	)
	print(f"Vendored {wheelPath.name} into {TARGET}")


if __name__ == "__main__":
	if len(sys.argv) != 2:
		sys.exit(__doc__)
	vendor(Path(sys.argv[1]).resolve())
