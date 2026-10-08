"""Verify an installed image/environment against the reviewed runtime pins."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys


def check(lock: Path) -> list[str]:
    errors = []
    for line in lock.read_text(encoding="utf-8").splitlines():
        pin = line.strip()
        if not pin or pin.startswith("#"):
            continue
        name, expected = pin.split("==", 1)
        try:
            actual = version(name)
        except PackageNotFoundError:
            errors.append(f"{name}: missing (expected {expected})")
            continue
        if actual != expected:
            errors.append(f"{name}: installed {actual}, expected {expected}")
    return errors


if __name__ == "__main__":
    errors = check(Path(sys.argv[1]))
    if errors:
        sys.exit("Runtime lock mismatch:\n" + "\n".join(errors))
    print("Runtime dependencies match reviewed pins.")
