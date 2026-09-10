"""Validate the production capability registry and its generated docs/CAPABILITIES.md view.

    python scripts/check-capabilities.py            # check (CI mode)
    python scripts/check-capabilities.py --write    # regenerate the block in docs/CAPABILITIES.md

The detailed capability contract is derived from
`apps/backend/app/extraction/support_matrix.py` and spliced into the marked block
in `docs/CAPABILITIES.md`. The prose around that block is hand-written; only the
block is generated and drift-checked.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_DOC = ROOT / "docs" / "CAPABILITIES.md"

sys.path.insert(0, str(ROOT / "apps/backend"))
sys.path.insert(0, str(ROOT / "apps/backend/tests"))

from app.extraction.support_matrix import (  # noqa: E402
    check_capabilities_doc,
    render_capabilities_block,
    splice_capabilities_block,
    validate_registry,
)
from benchmark.loader import load_support_matrix  # noqa: E402
from benchmark.paths import SUPPORT_MATRIX_PATH  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    write = "--write" in argv

    validate_registry()

    first = render_capabilities_block()
    second = render_capabilities_block()
    if first != second:
        raise SystemExit("capability block rendering is not deterministic")

    if write:
        current = CAPABILITIES_DOC.read_text(encoding="utf-8")
        updated = splice_capabilities_block(current)
        if updated != current:
            CAPABILITIES_DOC.write_text(updated, encoding="utf-8")
            print(f"Updated {CAPABILITIES_DOC.relative_to(ROOT)}")
        else:
            print(f"{CAPABILITIES_DOC.relative_to(ROOT)} already current")
    else:
        check_capabilities_doc(CAPABILITIES_DOC)

    matrix = load_support_matrix(SUPPORT_MATRIX_PATH)
    if not matrix.constructs:
        raise SystemExit("benchmark capability mapping is empty")

    print(f"Capability registry valid: {len(matrix.constructs)} benchmark mappings")
    if not write:
        print("docs/CAPABILITIES.md capability registry is current and deterministic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
