"""Validate the production capability registry and its checked-in README view."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))
sys.path.insert(0, str(ROOT / "apps/backend/tests"))

from app.extraction.support_matrix import (  # noqa: E402
    check_readme_capabilities,
    render_readme_capabilities,
    validate_registry,
)
from benchmark.loader import load_support_matrix  # noqa: E402
from benchmark.paths import SUPPORT_MATRIX_PATH  # noqa: E402


def main() -> int:
    validate_registry()
    first = render_readme_capabilities()
    second = render_readme_capabilities()
    if first != second:
        raise SystemExit("capability README rendering is not deterministic")
    check_readme_capabilities(ROOT / "README.md")
    matrix = load_support_matrix(SUPPORT_MATRIX_PATH)
    if not matrix.constructs:
        raise SystemExit("benchmark capability mapping is empty")
    print(f"Capability registry valid: {len(matrix.constructs)} benchmark mappings")
    print("README capability registry is current and deterministic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
