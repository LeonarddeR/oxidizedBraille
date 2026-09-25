"""Copy the installed louis_py package into the add-on.

Usage: uv run python scripts/copyLouisPy.py
"""

from __future__ import annotations

import shutil
import sys
from importlib.metadata import distribution
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "addon" / "globalPlugins" / "oxidizedBraille" / "louis_py"
SKIPPED_SUFFIXES = (".pdb", ".pyc")


def copyLouisPy() -> None:
	dist = distribution("louis-py")
	shutil.rmtree(TARGET, ignore_errors=True)
	TARGET.mkdir(parents=True)
	for file in dist.files or []:
		if file.parts[-2:] == ("licenses", "LICENSE"):
			destination = TARGET / "LICENSE"
		elif (
			file.parts[0] == "louis_py"
			and "__pycache__" not in file.parts
			and file.suffix not in SKIPPED_SUFFIXES
		):
			destination = TARGET.joinpath(*file.parts[1:])
		else:
			continue
		destination.parent.mkdir(parents=True, exist_ok=True)
		shutil.copyfile(file.locate(), destination)
	for required in ("_louis_py.pyd", "LICENSE"):
		if not (TARGET / required).is_file():
			sys.exit(f"louis-py {dist.version} did not provide {required}")
	print(f"Copied louis_py {dist.version} into {TARGET}")


if __name__ == "__main__":
	copyLouisPy()
