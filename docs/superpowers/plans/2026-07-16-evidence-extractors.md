# Evidence-backed TS/Python Extractors — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace regex symbol extraction (TypeScript and Python only) with two real extractors that emit RFC-0001 `observed` nodes and `observation` records, each carrying a valid line span, against a published support matrix — with diagnostics for unsupported constructs instead of silent drops or guesses.

**Architecture:** A shared `apps/backend/app/extraction/` package. `base.py` holds the `Extractor` protocol, result dataclasses, source decoding, span/path validation, and diagnostic codes; `naming.py` holds the qualified-name + discriminator helpers. `python.py` uses the stdlib `ast` module; `typescript.py` uses tree-sitter, walking named nodes by type (rather than `.scm` query files — a plain type-walk is simpler and more robust across grammar versions, and the "named support matrix" criterion is met explicitly by `support_matrix.py` + a parity test). Extractors emit `observed` facts only (no `resolved` edges — that is #91). Output dataclasses map one-to-one onto the merged `SnapshotStore` from #88.

**Tech Stack:** Python 3.12+ stdlib `ast`; `tree-sitter` (already pinned) + `tree-sitter-typescript` grammar; pytest; SQLAlchemy/SQLite for the `SnapshotStore` integration tests.

## Global Constraints

- Python floor is **3.12** (`requires-python = ">=3.12,<3.14"`). `ast.end_lineno` and `X | None` are available; do not add compatibility shims for older Pythons.
- **Extractors emit `observed` nodes and `observation` records only.** Never emit a `resolved`/`inferred` fact or an edge — RFC-0001 §7.2 forbids it for extractors; resolution is #91.
- **Scope is extraction correctness only.** Do not wire extractors into `POST /repositories/*`, `/analysis/{id}/start`, or `engine.py`'s build path. Production wiring is #93.
- **TypeScript = `.ts`/`.tsx` only. Python = `.py` only.** No `.js`/`.jsx`, no third language.
- **Lines are one-based and inclusive.** `logical_line_count = 1 + text.count("\n")` over a strict UTF-8 decode (RFC §6.2). Empty file = 1 logical line.
- **Paths are repository-relative POSIX, normalized via `canonical.normalize_repo_path`** (RFC §4.2). A path that escapes root → `RI-SEC-PATH-ESCAPE`, drop the fact.
- **Diagnostics are opt-in per declared blind spot** — no generic "unmatched node" fallback. Extractors emit only non-fatal severities.
- **Producer identifier** is `f"{extractor.name}@{extractor.version}"`, e.g. `python-ast@1.0.0`, `typescript-ast@1.0.0`.
- **Commit identity:** author `shauryaksharma24@gmail.com`; **no** AI/Claude attribution trailer in any commit.
- **Run tests from `apps/backend`** with the backend venv active: `apps/backend/.venv/Scripts/python.exe -m pytest ...` (Windows). All `pytest`/`python` commands below assume CWD = `apps/backend` and that interpreter.

---

## Phase A — Foundation + Python extractor (settles the shared interface)

### Task A1: Add the tree-sitter-typescript grammar dependency

**Files:**
- Modify: `apps/backend/pyproject.toml` (dependencies list, near line 21)
- Modify: `apps/backend/requirements.txt` (add pinned grammar)

**Interfaces:**
- Produces: an importable `tree_sitter` and `tree_sitter_typescript` in the backend venv.

- [ ] **Step 1: Add the grammar to `pyproject.toml`**

In `apps/backend/pyproject.toml`, in the `dependencies` array, immediately after the existing `"tree-sitter>=0.22.0",` line, add:

```toml
  "tree-sitter-typescript>=0.23.0",
```

- [ ] **Step 2: Install into the backend venv**

Run (CWD `apps/backend`):
```bash
.venv/Scripts/python.exe -m pip install "tree-sitter-typescript>=0.23.0"
```
Expected: installs `tree-sitter-typescript` and a compatible `tree-sitter` wheel.

- [ ] **Step 3: Verify both import and a parser can be built**

Run:
```bash
.venv/Scripts/python.exe -c "import tree_sitter_typescript as t; from tree_sitter import Language, Parser; Parser(Language(t.language_tsx())); print('ok')"
```
Expected: prints `ok`. (If `Language(...)`/`Parser(...)` raise a signature error, the installed `tree-sitter` core is <0.22; upgrade it: `.venv/Scripts/python.exe -m pip install "tree-sitter>=0.22,<0.26"`.)

- [ ] **Step 4: Pin in `requirements.txt`**

Determine the installed versions:
```bash
.venv/Scripts/python.exe -m pip show tree-sitter tree-sitter-typescript | grep -E "^(Name|Version)"
```
Add a line to `apps/backend/requirements.txt` next to the existing `tree-sitter==...` pin:
```
tree-sitter-typescript==<version-from-pip-show>
```
If `pip show` reports a different `tree-sitter` version than the existing pin, update that pin to match too.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/pyproject.toml apps/backend/requirements.txt
git commit -m "build(extraction): add tree-sitter-typescript grammar dependency"
```

---

### Task A2: `base.py` data model and `Extractor` protocol

**Files:**
- Create: `apps/backend/app/extraction/__init__.py`
- Create: `apps/backend/app/extraction/base.py`
- Test: `apps/backend/tests/extraction/__init__.py` (empty), `apps/backend/tests/extraction/test_base_model.py`

**Interfaces:**
- Produces: `ExtractedEvidence`, `ExtractedNode`, `ExtractedObservation`, `ExtractedDiagnostic`, `ExtractionResult` (frozen dataclasses); `Extractor` (Protocol) with `name: str`, `version: str`, `supports(path) -> bool`, `extract(path, source: bytes) -> ExtractionResult`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/__init__.py` (empty file), then `apps/backend/tests/extraction/test_base_model.py`:

```python
import dataclasses

import pytest

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedEvidence,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
)


def test_result_types_are_frozen_and_carry_expected_fields():
    ev = ExtractedEvidence(
        path="src/main.py", start_line=1, end_line=1, logical_line_count=1
    )
    node = ExtractedNode(
        node_kind="file", stable_key="file:src/main.py", name="main.py",
        language="python", evidence=(ev,),
    )
    obs = ExtractedObservation(
        observed_kind="import", subject_kind="file",
        subject_key="file:src/main.py", referent_text="os", ordinal=1, evidence=ev,
    )
    diag = ExtractedDiagnostic(
        code="RI-EXT-UNSUPPORTED", category="unsupported construct",
        severity="info", message="star import is unsupported",
    )
    result = ExtractionResult(nodes=(node,), observations=(obs,), diagnostics=(diag,))

    assert result.nodes[0].stable_key == "file:src/main.py"
    assert result.observations[0].referent_text == "os"
    assert result.diagnostics[0].severity == "info"
    assert ev.granularity == "span"  # default
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.name = "other"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_base_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.extraction'`.

- [ ] **Step 3: Write the module**

Create `apps/backend/app/extraction/__init__.py`:

```python
from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedEvidence,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
    Extractor,
)

__all__ = [
    "ExtractedDiagnostic",
    "ExtractedEvidence",
    "ExtractedNode",
    "ExtractedObservation",
    "ExtractionResult",
    "Extractor",
]
```

Create `apps/backend/app/extraction/base.py`:

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ExtractedEvidence:
    path: str  # repository-relative POSIX, normalized (RFC §4.2)
    start_line: int  # one-based
    end_line: int  # one-based, inclusive
    logical_line_count: int
    granularity: str = "span"  # "span" | "file"


@dataclass(frozen=True)
class ExtractedNode:
    node_kind: str  # "file" | "module" | "symbol" | "dependency"
    stable_key: str  # normalized per RFC §4.3
    name: str | None
    language: str | None
    evidence: tuple[ExtractedEvidence, ...]
    properties: Mapping[str, object] | None = None


@dataclass(frozen=True)
class ExtractedObservation:
    observed_kind: str  # "definition" | "import" | "call" | "route" | ...
    subject_kind: str
    subject_key: str
    referent_text: str | None
    ordinal: int
    evidence: ExtractedEvidence


@dataclass(frozen=True)
class ExtractedDiagnostic:
    code: str
    category: str
    severity: str  # fatal | error | warning | info
    message: str
    path: str | None = None
    span: tuple[int, int] | None = None
    subject: str | None = None
    details: Mapping[str, object] | None = None


@dataclass(frozen=True)
class ExtractionResult:
    nodes: tuple[ExtractedNode, ...] = ()
    observations: tuple[ExtractedObservation, ...] = ()
    diagnostics: tuple[ExtractedDiagnostic, ...] = ()


@runtime_checkable
class Extractor(Protocol):
    name: str
    version: str

    def supports(self, path: str) -> bool: ...

    def extract(self, path: str, source: bytes) -> ExtractionResult: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_base_model.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/__init__.py apps/backend/app/extraction/base.py apps/backend/tests/extraction/__init__.py apps/backend/tests/extraction/test_base_model.py
git commit -m "feat(extraction): add shared result model and Extractor protocol"
```

---

### Task A3: Source decoding, logical line count, binary/malformed diagnostics

**Files:**
- Modify: `apps/backend/app/extraction/base.py`
- Test: `apps/backend/tests/extraction/test_base_source.py`

**Interfaces:**
- Consumes: `ExtractedDiagnostic` (Task A2).
- Produces: `DIAGNOSTIC_CATEGORIES` constants and code constants (`RI_SRC_BINARY`, `RI_SRC_MALFORMED`, `RI_EXT_UNSUPPORTED`, `RI_SPAN_INVALID`, `RI_SEC_PATH_ESCAPE`, `RI_KEY_DUP_SYMBOL`); `logical_line_count(text: str) -> int`; `decode_source(path: str, source: bytes, *, producer: str) -> tuple[str | None, ExtractedDiagnostic | None]`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_base_source.py`:

```python
from app.extraction.base import decode_source, logical_line_count


def test_logical_line_count_matches_rfc_convention():
    assert logical_line_count("") == 1          # empty file = 1 logical line
    assert logical_line_count("a") == 1
    assert logical_line_count("a\n") == 2       # trailing newline = final empty line
    assert logical_line_count("a\r\nb") == 2    # \r\n counts once (only \n)
    assert logical_line_count("a\nb\nc") == 3


def test_decode_source_accepts_utf8_text():
    text, diag = decode_source("src/main.py", b"print('hi')\n", producer="python-ast@1.0.0")
    assert text == "print('hi')\n"
    assert diag is None


def test_decode_source_flags_binary_with_nul_byte():
    text, diag = decode_source("logo.png", b"\x89PNG\x00\x00", producer="python-ast@1.0.0")
    assert text is None
    assert diag is not None
    assert diag.code == "RI-SRC-BINARY"
    assert diag.severity == "info"
    assert diag.path == "logo.png"


def test_decode_source_flags_malformed_utf8_as_error():
    text, diag = decode_source("bad.py", b"\xff\xfe\x00bad", producer="python-ast@1.0.0")
    # \x00 present -> binary takes precedence per RFC (NUL => binary)
    assert diag.code == "RI-SRC-BINARY"

    text2, diag2 = decode_source("bad2.py", b"\xff\xfeabc", producer="python-ast@1.0.0")
    assert text2 is None
    assert diag2.code == "RI-SRC-MALFORMED"
    assert diag2.severity == "error"


def test_empty_file_decodes_to_text_not_binary():
    text, diag = decode_source("empty.py", b"", producer="python-ast@1.0.0")
    assert text == ""
    assert diag is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_base_source.py -v`
Expected: FAIL — `ImportError: cannot import name 'decode_source'`.

- [ ] **Step 3: Add the constants and functions to `base.py`**

Append to `apps/backend/app/extraction/base.py`:

```python
# --- Diagnostic codes (RFC §8.2) -------------------------------------------

RI_SRC_BINARY = "RI-SRC-BINARY"
RI_SRC_MALFORMED = "RI-SRC-MALFORMED"
RI_EXT_UNSUPPORTED = "RI-EXT-UNSUPPORTED"
RI_SPAN_INVALID = "RI-SPAN-INVALID"
RI_SEC_PATH_ESCAPE = "RI-SEC-PATH-ESCAPE"
RI_KEY_DUP_SYMBOL = "RI-KEY-DUP-SYMBOL"

_CATEGORY = {
    RI_SRC_BINARY: "binary source",
    RI_SRC_MALFORMED: "malformed source",
    RI_EXT_UNSUPPORTED: "unsupported construct",
    RI_SPAN_INVALID: "invalid span",
    RI_SEC_PATH_ESCAPE: "path escape",
    RI_KEY_DUP_SYMBOL: "duplicate symbol",
}


def logical_line_count(text: str) -> int:
    """RFC §6.2: one logical line per file, plus one per U+000A."""

    return 1 + text.count("\n")


def decode_source(
    path: str, source: bytes, *, producer: str
) -> tuple[str | None, ExtractedDiagnostic | None]:
    """Strict UTF-8 decode with RFC §6.2 binary/malformed handling.

    Returns ``(text, None)`` for decodable text (a zero-byte file decodes to
    ``""``), or ``(None, diagnostic)`` when the file is binary (contains a NUL
    byte) or is not valid UTF-8.
    """

    if b"\x00" in source:
        return None, ExtractedDiagnostic(
            code=RI_SRC_BINARY,
            category=_CATEGORY[RI_SRC_BINARY],
            severity="info",
            message="file contains a NUL byte and is excluded from line-addressed extraction",
            path=path,
        )
    try:
        return source.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, ExtractedDiagnostic(
            code=RI_SRC_MALFORMED,
            category=_CATEGORY[RI_SRC_MALFORMED],
            severity="error",
            message="file is not valid UTF-8 and could not be decoded",
            path=path,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_base_source.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/base.py apps/backend/tests/extraction/test_base_source.py
git commit -m "feat(extraction): add source decode, line count, and source diagnostics"
```

---

### Task A4: Evidence construction with span + path validation

**Files:**
- Modify: `apps/backend/app/extraction/base.py`
- Test: `apps/backend/tests/extraction/test_base_evidence.py`

**Interfaces:**
- Consumes: `ExtractedEvidence`, `ExtractedDiagnostic`, code constants (Tasks A2–A3), `app.intelligence.canonical.normalize_repo_path` / `PathEscapeError`.
- Produces: `build_evidence(path, start_line, end_line, logical_line_count, *, producer, granularity="span") -> tuple[ExtractedEvidence | None, ExtractedDiagnostic | None]`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_base_evidence.py`:

```python
from app.extraction.base import build_evidence


def test_valid_span_builds_normalized_evidence():
    ev, diag = build_evidence(
        "src/./auth/service.ts", 41, 58, 100, producer="typescript-ast@1.0.0"
    )
    assert diag is None
    assert ev.path == "src/auth/service.ts"  # normalized
    assert (ev.start_line, ev.end_line, ev.logical_line_count) == (41, 58, 100)


def test_reversed_or_out_of_range_span_is_rejected():
    ev, diag = build_evidence("a.py", 10, 5, 100, producer="python-ast@1.0.0")
    assert ev is None and diag.code == "RI-SPAN-INVALID" and diag.severity == "error"

    ev2, diag2 = build_evidence("a.py", 1, 200, 100, producer="python-ast@1.0.0")
    assert ev2 is None and diag2.code == "RI-SPAN-INVALID"


def test_escaping_path_is_rejected():
    ev, diag = build_evidence("../secrets/.env", 1, 1, 1, producer="python-ast@1.0.0")
    assert ev is None and diag.code == "RI-SEC-PATH-ESCAPE"


def test_file_granularity_is_carried_through():
    ev, diag = build_evidence(
        "empty.py", 1, 1, 1, producer="python-ast@1.0.0", granularity="file"
    )
    assert diag is None and ev.granularity == "file"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_base_evidence.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_evidence'`.

- [ ] **Step 3: Add `build_evidence` to `base.py`**

Add near the top of `apps/backend/app/extraction/base.py`, after the existing imports:

```python
from app.intelligence import canonical
```

Append this function:

```python
def build_evidence(
    path: str,
    start_line: int,
    end_line: int,
    logical_line_count: int,
    *,
    producer: str,
    granularity: str = "span",
) -> tuple[ExtractedEvidence | None, ExtractedDiagnostic | None]:
    """Validate a span and path (RFC §4.2, §6.2), returning evidence or a diagnostic.

    ``producer`` is the ``name@version`` identifier, carried into the diagnostic
    so callers do not have to duplicate it.
    """

    try:
        normalized = canonical.normalize_repo_path(path)
    except canonical.PathEscapeError:
        return None, ExtractedDiagnostic(
            code=RI_SEC_PATH_ESCAPE,
            category=_CATEGORY[RI_SEC_PATH_ESCAPE],
            severity="error",
            message="evidence path is absolute or escapes the repository root",
            path=None,
        )
    if not (1 <= start_line <= end_line <= logical_line_count):
        return None, ExtractedDiagnostic(
            code=RI_SPAN_INVALID,
            category=_CATEGORY[RI_SPAN_INVALID],
            severity="error",
            message=(
                f"span {start_line}..{end_line} is not within 1..{logical_line_count}"
            ),
            path=normalized,
            span=(start_line, end_line),
        )
    return (
        ExtractedEvidence(
            path=normalized,
            start_line=start_line,
            end_line=end_line,
            logical_line_count=logical_line_count,
            granularity=granularity,
        ),
        None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_base_evidence.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/base.py apps/backend/tests/extraction/test_base_evidence.py
git commit -m "feat(extraction): add span- and path-validated evidence builder"
```

---

### Task A5: Qualified-name scope stack + duplicate discriminator

**Files:**
- Create: `apps/backend/app/extraction/naming.py`
- Test: `apps/backend/tests/extraction/test_naming.py`

**Interfaces:**
- Consumes: `canonical.normalize_repo_path`.
- Produces: `symbol_stable_key(path: str, scope: Sequence[str], name: str) -> str` (joins scope + name with `.`, prefixes normalized file path + `::`); `DiscriminatorAssigner` with `.key(base_symbol_key: str) -> tuple[str, bool]` returning `(final_key, was_duplicate)` where the first occurrence returns the base key and later ones append `#2`, `#3`, … in call order.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_naming.py`:

```python
from app.extraction.naming import DiscriminatorAssigner, symbol_stable_key


def test_symbol_stable_key_builds_qualified_dotted_name():
    assert symbol_stable_key("src/auth/service.ts", [], "issueToken") == \
        "src/auth/service.ts::issueToken"
    assert symbol_stable_key("src/auth/service.ts", ["AuthService"], "login") == \
        "src/auth/service.ts::AuthService.login"
    assert symbol_stable_key("app/api/auth.py", ["outer"], "_inner") == \
        "app/api/auth.py::outer._inner"


def test_discriminator_numbers_duplicates_in_source_order():
    assigner = DiscriminatorAssigner()
    base = "a.ts::fmt"
    assert assigner.key(base) == ("a.ts::fmt", False)
    assert assigner.key(base) == ("a.ts::fmt#2", True)
    assert assigner.key(base) == ("a.ts::fmt#3", True)
    # a different key is independent
    assert assigner.key("a.ts::other") == ("a.ts::other", False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_naming.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.extraction.naming'`.

- [ ] **Step 3: Write `naming.py`**

Create `apps/backend/app/extraction/naming.py`:

```python
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.intelligence import canonical


def symbol_stable_key(path: str, scope: Sequence[str], name: str) -> str:
    """Build ``<file-path>::<qualified.name>`` (RFC §4.3), path normalized."""

    normalized = canonical.normalize_repo_path(path)
    qualified = ".".join([*scope, name])
    return f"{normalized}::{qualified}"


class DiscriminatorAssigner:
    """Assigns RFC §4.3 ``#<n>`` discriminators by source order within one file.

    The first occurrence of a base symbol key is returned unchanged; each later
    occurrence gets ``#2``, ``#3``, … The second return value is ``True`` when a
    discriminator was appended, so the caller can emit an ``RI-KEY-DUP-SYMBOL``
    diagnostic. Instantiate one per file so counters are revision-local.
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)

    def key(self, base_symbol_key: str) -> tuple[str, bool]:
        self._counts[base_symbol_key] += 1
        n = self._counts[base_symbol_key]
        if n == 1:
            return base_symbol_key, False
        return f"{base_symbol_key}#{n}", True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_naming.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/naming.py apps/backend/tests/extraction/test_naming.py
git commit -m "feat(extraction): add qualified-name and duplicate-discriminator helpers"
```

---

### Task A6: Python extractor — module node + import observations

**Files:**
- Create: `apps/backend/app/extraction/python.py`
- Test: `apps/backend/tests/extraction/test_python_extractor.py`

**Interfaces:**
- Consumes: everything in `base.py` and `naming.py`.
- Produces: `PythonExtractor` with `name="python-ast"`, `version="1.0.0"`, `supports(path)`, `extract(path, source)`; emits a `module` node (whole-file evidence) and one `import` observation per imported name.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_python_extractor.py`:

```python
from app.extraction.python import PythonExtractor

EXTRACTOR = PythonExtractor()


def _extract(source: str):
    return EXTRACTOR.extract("app/api/auth.py", source.encode("utf-8"))


def test_supports_only_python():
    assert EXTRACTOR.supports("a.py") is True
    assert EXTRACTOR.supports("a.ts") is False


def test_module_node_has_whole_file_evidence():
    result = _extract("import os\n")
    modules = [n for n in result.nodes if n.node_kind == "module"]
    assert len(modules) == 1
    module = modules[0]
    assert module.stable_key == "mod:app/api"
    ev = module.evidence[0]
    assert ev.granularity == "file"
    assert (ev.start_line, ev.end_line) == (1, ev.logical_line_count)


def test_imports_become_observations_with_referent_text():
    result = _extract("import os\nfrom app.core import config\n")
    imports = sorted(
        (o.referent_text for o in result.observations if o.observed_kind == "import")
    )
    assert imports == ["app.core.config", "os"]
    for obs in result.observations:
        if obs.observed_kind == "import":
            assert obs.subject_key == "mod:app/api"
            assert obs.evidence.start_line >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_python_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.extraction.python'`.

- [ ] **Step 3: Write the module skeleton + imports**

Create `apps/backend/app/extraction/python.py`:

```python
from __future__ import annotations

import ast
import posixpath

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
    RI_SRC_MALFORMED,
    build_evidence,
    decode_source,
    logical_line_count,
)
from app.intelligence import canonical


class PythonExtractor:
    name = "python-ast"
    version = "1.0.0"

    @property
    def producer(self) -> str:
        return f"{self.name}@{self.version}"

    def supports(self, path: str) -> bool:
        return path.endswith(".py")

    def extract(self, path: str, source: bytes) -> ExtractionResult:
        text, source_diag = decode_source(path, source, producer=self.producer)
        if text is None:
            return ExtractionResult(diagnostics=(source_diag,))

        line_count = logical_line_count(text)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SRC_MALFORMED,
                        category="malformed source",
                        severity="error",
                        message="file could not be parsed as Python",
                        path=canonical.normalize_repo_path(path),
                    ),
                )
            )

        nodes: list[ExtractedNode] = []
        observations: list[ExtractedObservation] = []
        diagnostics: list[ExtractedDiagnostic] = []

        module_key = self._module_key(path)
        module_ev, module_ev_diag = build_evidence(
            path, 1, line_count, line_count, producer=self.producer, granularity="file"
        )
        if module_ev is not None:
            nodes.append(
                ExtractedNode(
                    node_kind="module",
                    stable_key=module_key,
                    name=posixpath.basename(canonical.normalize_repo_path(path)),
                    language="python",
                    evidence=(module_ev,),
                )
            )
        elif module_ev_diag is not None:
            diagnostics.append(module_ev_diag)

        self._collect_imports(
            tree, path, line_count, module_key, observations, diagnostics
        )

        return ExtractionResult(
            nodes=tuple(nodes),
            observations=tuple(observations),
            diagnostics=tuple(diagnostics),
        )

    def _module_key(self, path: str) -> str:
        directory = posixpath.dirname(canonical.normalize_repo_path(path))
        return canonical.normalize_stable_key("module", f"mod:{directory}")

    def _collect_imports(
        self, tree, path, line_count, module_key, observations, diagnostics
    ) -> None:
        ordinal = 0
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                names = [
                    f"{base}.{alias.name}" if base else alias.name
                    for alias in node.names
                    if alias.name != "*"
                ]
            else:
                continue
            for name in names:
                ordinal += 1
                ev, diag = build_evidence(
                    path, node.lineno, node.end_lineno or node.lineno, line_count,
                    producer=self.producer,
                )
                if ev is None:
                    if diag is not None:
                        diagnostics.append(diag)
                    continue
                observations.append(
                    ExtractedObservation(
                        observed_kind="import",
                        subject_kind="module",
                        subject_key=module_key,
                        referent_text=name,
                        ordinal=ordinal,
                        evidence=ev,
                    )
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_python_extractor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/python.py apps/backend/tests/extraction/test_python_extractor.py
git commit -m "feat(extraction): Python extractor emits module node and import observations"
```

---

### Task A7: Python extractor — functions, classes, methods, definition observations

**Files:**
- Modify: `apps/backend/app/extraction/python.py`
- Test: `apps/backend/tests/extraction/test_python_symbols.py`

**Interfaces:**
- Consumes: `symbol_stable_key`, `DiscriminatorAssigner` (Task A5).
- Produces: for each `def`/`async def`/`class`, a `symbol` node with a qualified stable key + a `definition` observation; nested scopes reflected in the qualified name; `RI-KEY-DUP-SYMBOL` for duplicates.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_python_symbols.py`:

```python
from app.extraction.python import PythonExtractor

EXTRACTOR = PythonExtractor()


def _keys(source: str):
    result = EXTRACTOR.extract("app/api/auth.py", source.encode("utf-8"))
    return {n.stable_key for n in result.nodes if n.node_kind == "symbol"}, result


def test_class_method_and_nested_function_qualified_names():
    keys, _ = _keys(
        "class AuthController:\n"
        "    def login(self):\n"
        "        pass\n"
        "def outer():\n"
        "    def _inner():\n"
        "        pass\n"
    )
    assert "app/api/auth.py::AuthController" in keys
    assert "app/api/auth.py::AuthController.login" in keys
    assert "app/api/auth.py::outer" in keys
    assert "app/api/auth.py::outer._inner" in keys


def test_duplicate_defs_get_discriminator_and_diagnostic():
    keys, result = _keys("def handler():\n    pass\ndef handler():\n    pass\n")
    assert "app/api/auth.py::handler" in keys
    assert "app/api/auth.py::handler#2" in keys
    assert any(d.code == "RI-KEY-DUP-SYMBOL" for d in result.diagnostics)


def test_each_symbol_has_a_definition_observation():
    _, result = _keys("def get_current_user():\n    pass\n")
    defs = [o for o in result.observations if o.observed_kind == "definition"]
    assert any(o.subject_key == "app/api/auth.py::get_current_user" for o in defs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_python_symbols.py -v`
Expected: FAIL — nested/qualified symbol keys are not produced yet.

- [ ] **Step 3: Add a scope-walking visitor to `python.py`**

Add these imports at the top of `apps/backend/app/extraction/python.py`:

```python
from app.extraction.base import RI_KEY_DUP_SYMBOL
from app.extraction.naming import DiscriminatorAssigner, symbol_stable_key
```

In `extract`, after the `_collect_imports(...)` call and before the `return`, add:

```python
        self._collect_symbols(
            tree, path, line_count, nodes, observations, diagnostics
        )
```

Add these methods to `PythonExtractor`:

```python
    _DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def _collect_symbols(
        self, tree, path, line_count, nodes, observations, diagnostics
    ) -> None:
        assigner = DiscriminatorAssigner()
        ordinal = 0

        def visit(scope: list[str], body) -> None:
            nonlocal ordinal
            for child in body:
                if not isinstance(child, self._DEF_TYPES):
                    continue
                base_key = symbol_stable_key(path, scope, child.name)
                final_key, duplicate = assigner.key(base_key)
                ev, diag = build_evidence(
                    path, child.lineno, child.end_lineno or child.lineno,
                    line_count, producer=self.producer,
                )
                if ev is None:
                    if diag is not None:
                        diagnostics.append(diag)
                else:
                    nodes.append(
                        ExtractedNode(
                            node_kind="symbol",
                            stable_key=canonical.normalize_stable_key("symbol", final_key),
                            name=child.name,
                            language="python",
                            evidence=(ev,),
                        )
                    )
                    ordinal += 1
                    observations.append(
                        ExtractedObservation(
                            observed_kind="definition",
                            subject_kind="symbol",
                            subject_key=canonical.normalize_stable_key("symbol", final_key),
                            referent_text=None,
                            ordinal=ordinal,
                            evidence=ev,
                        )
                    )
                if duplicate:
                    diagnostics.append(
                        ExtractedDiagnostic(
                            code=RI_KEY_DUP_SYMBOL,
                            category="duplicate symbol",
                            severity="info",
                            message=f"duplicate symbol name resolved with a discriminator: {final_key}",
                            path=canonical.normalize_repo_path(path),
                            subject=canonical.normalize_stable_key("symbol", final_key),
                        )
                    )
                visit([*scope, child.name], child.body)

        visit([], tree.body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_python_symbols.py -v`
Expected: PASS. Also run the Task A6 test to confirm no regression: `.venv/Scripts/python.exe -m pytest tests/extraction/test_python_extractor.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/python.py apps/backend/tests/extraction/test_python_symbols.py
git commit -m "feat(extraction): Python extractor emits qualified symbol nodes and definitions"
```

---

### Task A8: Python extractor — decorators as property + FastAPI route observations

**Files:**
- Modify: `apps/backend/app/extraction/python.py`
- Test: `apps/backend/tests/extraction/test_python_routes.py`

**Interfaces:**
- Produces: decorated symbols carry `properties={"decorators": [<names>], "exported": ...}`; a FastAPI-style route decorator (`@router.post("/login")`) yields a `route` observation whose `referent_text` is the **literal path string only** (no prefix joining — that is #91).

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_python_routes.py`:

```python
from app.extraction.python import PythonExtractor

EXTRACTOR = PythonExtractor()


def _extract(source: str):
    return EXTRACTOR.extract("app/api/auth.py", source.encode("utf-8"))


def test_decorators_are_recorded_as_a_symbol_property():
    result = _extract(
        "import functools\n"
        "@functools.cache\n"
        "def compute():\n"
        "    pass\n"
    )
    compute = next(
        n for n in result.nodes
        if n.stable_key == "app/api/auth.py::compute"
    )
    assert compute.properties is not None
    assert "functools.cache" in compute.properties["decorators"]


def test_fastapi_route_decorator_yields_literal_path_observation():
    result = _extract(
        "router = APIRouter(prefix='/auth')\n"
        "@router.post('/login')\n"
        "def login():\n"
        "    pass\n"
    )
    routes = [o for o in result.observations if o.observed_kind == "route"]
    assert len(routes) == 1
    # literal decorator string only; no /auth prefix joined (that is #91)
    assert routes[0].referent_text == "/login"
    assert routes[0].subject_key == "app/api/auth.py::login"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_python_routes.py -v`
Expected: FAIL — no decorator property, no route observation.

- [ ] **Step 3: Extend the visitor with decorator + route handling**

Add a helper and extend `_collect_symbols` in `apps/backend/app/extraction/python.py`. First add this module-level constant near the top:

```python
_ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}
```

Then, inside `_collect_symbols`'s `visit`, after `final_key`/`ev` are computed and the symbol node is appended, replace the plain `ExtractedNode(...)` construction with one that attaches decorator properties, and emit route observations. Concretely, change the node append block to:

```python
                    decorators = [self._decorator_name(d) for d in getattr(child, "decorator_list", [])]
                    decorators = [d for d in decorators if d]
                    properties = {"decorators": decorators} if decorators else None
                    nodes.append(
                        ExtractedNode(
                            node_kind="symbol",
                            stable_key=canonical.normalize_stable_key("symbol", final_key),
                            name=child.name,
                            language="python",
                            evidence=(ev,),
                            properties=properties,
                        )
                    )
                    ordinal += 1
                    observations.append(
                        ExtractedObservation(
                            observed_kind="definition",
                            subject_kind="symbol",
                            subject_key=canonical.normalize_stable_key("symbol", final_key),
                            referent_text=None,
                            ordinal=ordinal,
                            evidence=ev,
                        )
                    )
                    for route_path, route_node in self._route_paths(child):
                        route_ev, route_diag = build_evidence(
                            path, route_node.lineno, route_node.end_lineno or route_node.lineno,
                            line_count, producer=self.producer,
                        )
                        if route_ev is None:
                            if route_diag is not None:
                                diagnostics.append(route_diag)
                            continue
                        ordinal += 1
                        observations.append(
                            ExtractedObservation(
                                observed_kind="route",
                                subject_kind="symbol",
                                subject_key=canonical.normalize_stable_key("symbol", final_key),
                                referent_text=route_path,
                                ordinal=ordinal,
                                evidence=route_ev,
                            )
                        )
```

Add these helper methods to `PythonExtractor`:

```python
    def _decorator_name(self, decorator) -> str | None:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        parts: list[str] = []
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        return ".".join(reversed(parts)) if parts else None

    def _route_paths(self, symbol):
        for decorator in getattr(symbol, "decorator_list", []):
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr not in _ROUTE_METHODS:
                continue
            if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                yield decorator.args[0].value, decorator
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_python_routes.py tests/extraction/test_python_symbols.py -v`
Expected: PASS (both files).

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/python.py apps/backend/tests/extraction/test_python_routes.py
git commit -m "feat(extraction): Python extractor records decorators and route observations"
```

---

### Task A9: Python extractor — blind-spot diagnostics

**Files:**
- Modify: `apps/backend/app/extraction/python.py`
- Test: `apps/backend/tests/extraction/test_python_diagnostics.py`

**Interfaces:**
- Produces: `RI-EXT-UNSUPPORTED` (info) for star-imports, dynamic imports (`importlib.import_module`, `__import__`), and reflection (`getattr`/`setattr`/`delattr`); each names the construct; no fabricated fact.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_python_diagnostics.py`:

```python
from app.extraction.python import PythonExtractor

EXTRACTOR = PythonExtractor()


def _codes(source: str):
    result = EXTRACTOR.extract("app/api/auth.py", source.encode("utf-8"))
    return [d.code for d in result.diagnostics], result


def test_star_import_is_flagged_unsupported():
    codes, result = _codes("from os import *\n")
    assert "RI-EXT-UNSUPPORTED" in codes
    # star import must not appear as a normal import observation
    assert all(o.referent_text != "*" for o in result.observations)


def test_dynamic_import_is_flagged():
    codes, _ = _codes("import importlib\nm = importlib.import_module('os')\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_reflection_is_flagged():
    codes, _ = _codes("x = getattr(object(), 'name', None)\n")
    assert "RI-EXT-UNSUPPORTED" in codes


def test_syntax_error_is_malformed_and_yields_no_symbols():
    result = EXTRACTOR.extract("bad.py", b"def broken(:\n")
    assert [d.code for d in result.diagnostics] == ["RI-SRC-MALFORMED"]
    assert result.nodes == () and result.observations == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_python_diagnostics.py -v`
Expected: FAIL — blind-spot diagnostics not emitted (syntax-error case already passes from Task A6).

- [ ] **Step 3: Add blind-spot detection**

In `apps/backend/app/extraction/python.py`, add to `extract` after `_collect_symbols(...)`:

```python
        self._collect_blind_spots(tree, path, line_count, diagnostics)
```

Add the module-level constant and method:

```python
_DYNAMIC_IMPORT_CALLS = {"import_module", "__import__"}
_REFLECTION_CALLS = {"getattr", "setattr", "delattr"}
```

```python
    def _collect_blind_spots(self, tree, path, line_count, diagnostics) -> None:
        normalized = canonical.normalize_repo_path(path)

        def flag(node, message: str) -> None:
            diagnostics.append(
                ExtractedDiagnostic(
                    code="RI-EXT-UNSUPPORTED",
                    category="unsupported construct",
                    severity="info",
                    message=message,
                    path=normalized,
                    span=(node.lineno, node.end_lineno or node.lineno),
                )
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                flag(node, f"star-import from {node.module or '.'} is unsupported")
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in _REFLECTION_CALLS:
                    flag(node, f"reflection via {func.id}() is unsupported")
                elif isinstance(func, ast.Name) and func.id == "__import__":
                    flag(node, "dynamic import via __import__() is unsupported")
                elif isinstance(func, ast.Attribute) and func.attr in _DYNAMIC_IMPORT_CALLS:
                    flag(node, f"dynamic import via {func.attr}() is unsupported")
```

Note: `RI_EXT_UNSUPPORTED` is already imported in Task A6's import block via `base`; if not, add it to the `from app.extraction.base import (...)` list.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_python_diagnostics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/python.py apps/backend/tests/extraction/test_python_diagnostics.py
git commit -m "feat(extraction): Python extractor emits blind-spot diagnostics"
```

---

### Task A10: Support matrix (Python) + parity test

**Files:**
- Create: `apps/backend/app/extraction/support_matrix.py`
- Test: `apps/backend/tests/extraction/test_support_matrix.py`

**Interfaces:**
- Produces: `SUPPORT_MATRIX: dict[str, LanguageSupport]` where `LanguageSupport` has `supported: tuple[str, ...]` and `unsupported: tuple[str, ...]`; `PYTHON` key populated.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_support_matrix.py`:

```python
from app.extraction.support_matrix import SUPPORT_MATRIX


def test_python_matrix_lists_supported_and_unsupported():
    python = SUPPORT_MATRIX["python"]
    assert "module" in python.supported
    assert "import" in python.supported
    assert "function" in python.supported
    assert "class" in python.supported
    assert "decorator" in python.supported
    assert "route" in python.supported
    assert "star-import" in python.unsupported
    assert "dynamic-import" in python.unsupported
    assert "reflection" in python.unsupported
    # nothing appears on both sides
    assert set(python.supported).isdisjoint(python.unsupported)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_support_matrix.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Write `support_matrix.py`**

Create `apps/backend/app/extraction/support_matrix.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageSupport:
    supported: tuple[str, ...]
    unsupported: tuple[str, ...]


SUPPORT_MATRIX: dict[str, LanguageSupport] = {
    "python": LanguageSupport(
        supported=("module", "import", "function", "class", "method", "decorator", "route"),
        unsupported=("star-import", "dynamic-import", "reflection", "metaclass"),
    ),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_support_matrix.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/support_matrix.py apps/backend/tests/extraction/test_support_matrix.py
git commit -m "feat(extraction): publish Python support matrix with parity test"
```

---

### Task A11: SnapshotStore integration — Python facts seal

**Files:**
- Test: `apps/backend/tests/extraction/test_python_snapshot_integration.py`

**Interfaces:**
- Consumes: `PythonExtractor`, and the merged `SnapshotStore`/`Evidence`/`Revision` (#88). Reuses the fixture pattern from `tests/test_snapshot_persistence.py`.
- Produces: proof that an `ExtractionResult` writes into a `building` snapshot and seals to `completed`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_python_snapshot_integration.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.extraction.python import PythonExtractor
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.base import Base

UPLOAD_REVISION = "sha256:" + "a" * 64


@pytest.fixture()
def session(tmp_path):
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'snap.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        yield db
    engine.dispose()


def _repository(session: Session) -> RepositoryRecord:
    owner = User(id=str(uuid4()), email="o@example.com", password_hash=None)
    session.add(owner)
    session.commit()
    record = RepositoryRecord(
        id=str(uuid4()), owner_id=owner.id, name="repo", source="upload",
        revision_kind="upload", revision_value=UPLOAD_REVISION,
        local_path="/x", status="completed", file_tree=[],
    )
    session.add(record)
    session.commit()
    return record


def _to_evidence(extracted) -> Evidence:
    return Evidence(
        path=extracted.path, start_line=extracted.start_line,
        end_line=extracted.end_line, extractor="python-ast",
        extractor_version="1.0.0", logical_line_count=extracted.logical_line_count,
        granularity=extracted.granularity,
    )


def test_python_extraction_result_seals_into_a_snapshot(session):
    repository = _repository(session)
    result = PythonExtractor().extract(
        "app/api/auth.py",
        b"import os\n\n\ndef get_current_user():\n    return None\n",
    )
    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=repository.id,
        revision=Revision("upload", UPLOAD_REVISION),
        producer_version_set=["python-ast@1.0.0"],
    )
    # a repo:root node is required for a coherent snapshot (RFC §11.2 rule 5)
    root_ev = Evidence(
        path="app/api/auth.py", start_line=1, end_line=1,
        extractor="python-ast", extractor_version="1.0.0",
        logical_line_count=5, granularity="file",
    )
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[root_ev])
    for node in result.nodes:
        store.add_node(
            snapshot, node_kind=node.node_kind, stable_key=node.stable_key,
            name=node.name, language=node.language,
            properties=node.properties,
            evidence=[_to_evidence(e) for e in node.evidence],
        )
    for obs in result.observations:
        store.add_observation(
            snapshot, observed_kind=obs.observed_kind, subject_kind=obs.subject_kind,
            subject_key=obs.subject_key, referent_text=obs.referent_text,
            ordinal=obs.ordinal, evidence=_to_evidence(obs.evidence),
        )
    for diag in result.diagnostics:
        store.add_diagnostic(
            snapshot, code=diag.code, category=diag.category, severity=diag.severity,
            message=diag.message, producer="python-ast@1.0.0", path=diag.path,
            span=diag.span, subject=diag.subject, details=diag.details,
        )

    sealed = store.seal(snapshot)
    assert sealed.state == "completed"
    assert sealed.canonical_graph_hash.startswith("sha256:")
```

- [ ] **Step 2: Run test to verify it fails, then passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_python_snapshot_integration.py -v`
Expected: If the extractor and store are correct, this PASSES immediately (no new production code — it wires existing pieces). If it FAILS with a `SnapshotSealError`, read the message: the most likely causes are an observation subject whose node was not added (add the missing node) or a `module` node used where the RFC expects `repo:root` — this test intentionally adds `repo:root` separately, so a failure here signals a real contract gap to fix in `python.py`.

- [ ] **Step 3: (If needed) fix the extractor to satisfy the seal contract**

Only if Step 2 failed: adjust `python.py` so every observation's `subject_key` refers to a node the result also emits (e.g. ensure the `module` node's `subject` linkage is consistent), then re-run. Do not weaken the store.

- [ ] **Step 4: Confirm green**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/ -v`
Expected: PASS (all extraction tests).

- [ ] **Step 5: Commit**

```bash
git add apps/backend/tests/extraction/test_python_snapshot_integration.py apps/backend/app/extraction/python.py
git commit -m "test(extraction): prove Python extraction seals into a snapshot"
```

---

## Phase B — TypeScript extractor (interface now settled)

### Task B1: TypeScript extractor scaffold — grammar load + file node

**Files:**
- Create: `apps/backend/app/extraction/typescript.py`
- Test: `apps/backend/tests/extraction/test_typescript_extractor.py`

**Interfaces:**
- Produces: `TypeScriptExtractor` with `name="typescript-ast"`, `version="1.0.0"`, `supports(path)` (`.ts`/`.tsx`), `extract(path, source)`; emits a `file` node with whole-file evidence; selects the `tsx` grammar for `.tsx` and `typescript` for `.ts`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_typescript_extractor.py`:

```python
from app.extraction.typescript import TypeScriptExtractor

EXTRACTOR = TypeScriptExtractor()


def _extract(path: str, source: str):
    return EXTRACTOR.extract(path, source.encode("utf-8"))


def test_supports_ts_and_tsx_only():
    assert EXTRACTOR.supports("a.ts") is True
    assert EXTRACTOR.supports("a.tsx") is True
    assert EXTRACTOR.supports("a.js") is False
    assert EXTRACTOR.supports("a.py") is False


def test_file_node_has_whole_file_evidence():
    result = _extract("src/main.ts", "const x = 1;\n")
    files = [n for n in result.nodes if n.node_kind == "file"]
    assert len(files) == 1
    assert files[0].stable_key == "file:src/main.ts"
    ev = files[0].evidence[0]
    assert ev.granularity == "file"
    assert (ev.start_line, ev.end_line) == (1, ev.logical_line_count)


def test_binary_file_is_flagged_not_parsed():
    result = _extract("src/blob.ts", "\x00\x00")
    assert [d.code for d in result.diagnostics] == ["RI-SRC-BINARY"]
    assert result.nodes == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_extractor.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Write the scaffold**

Create `apps/backend/app/extraction/typescript.py`:

```python
from __future__ import annotations

import posixpath

import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from app.extraction.base import (
    ExtractedNode,
    ExtractionResult,
    build_evidence,
    decode_source,
    logical_line_count,
)
from app.intelligence import canonical

_TS_LANGUAGE = Language(tsts.language_typescript())
_TSX_LANGUAGE = Language(tsts.language_tsx())


class TypeScriptExtractor:
    name = "typescript-ast"
    version = "1.0.0"

    @property
    def producer(self) -> str:
        return f"{self.name}@{self.version}"

    def supports(self, path: str) -> bool:
        return path.endswith(".ts") or path.endswith(".tsx")

    def _parser(self, path: str) -> Parser:
        return Parser(_TSX_LANGUAGE if path.endswith(".tsx") else _TS_LANGUAGE)

    def extract(self, path: str, source: bytes) -> ExtractionResult:
        text, source_diag = decode_source(path, source, producer=self.producer)
        if text is None:
            return ExtractionResult(diagnostics=(source_diag,))

        line_count = logical_line_count(text)
        tree = self._parser(path).parse(source)

        nodes: list[ExtractedNode] = []
        diagnostics = []

        file_key = canonical.normalize_stable_key(
            "file", f"file:{canonical.normalize_repo_path(path)}"
        )
        file_ev, file_diag = build_evidence(
            path, 1, line_count, line_count, producer=self.producer, granularity="file"
        )
        if file_ev is not None:
            nodes.append(
                ExtractedNode(
                    node_kind="file",
                    stable_key=file_key,
                    name=posixpath.basename(canonical.normalize_repo_path(path)),
                    language="typescript",
                    evidence=(file_ev,),
                )
            )
        elif file_diag is not None:
            diagnostics.append(file_diag)

        # tree is retained for construct queries added in later tasks.
        _ = tree
        return ExtractionResult(nodes=tuple(nodes), diagnostics=tuple(diagnostics))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_extractor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/typescript.py apps/backend/tests/extraction/test_typescript_extractor.py
git commit -m "feat(extraction): TypeScript extractor scaffold with file node"
```

---

### Task B2: TypeScript — symbols with qualified names + discriminators

**Files:**
- Modify: `apps/backend/app/extraction/typescript.py`
- Test: `apps/backend/tests/extraction/test_typescript_symbols.py`

**Interfaces:**
- Consumes: `symbol_stable_key`, `DiscriminatorAssigner`, `ExtractedObservation`.
- Produces: `symbol` nodes + `definition` observations for `function_declaration`, `class_declaration` (and its `method_definition`s), `interface_declaration`, `type_alias_declaration`, `enum_declaration`, and top-level `lexical_declaration` const bindings; qualified names via ancestor walk; `#<n>` discriminators + `RI-KEY-DUP-SYMBOL`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_typescript_symbols.py`:

```python
from app.extraction.typescript import TypeScriptExtractor

EXTRACTOR = TypeScriptExtractor()


def _keys(source: str):
    result = EXTRACTOR.extract("src/auth/service.ts", source.encode("utf-8"))
    return {n.stable_key for n in result.nodes if n.node_kind == "symbol"}, result


def test_class_methods_and_function_qualified_names():
    # Two methods prove the traversal reaches every method_definition inside
    # class_body, not just the class declaration itself.
    keys, _ = _keys(
        "export class AuthService {\n"
        "  login() {}\n"
        "  logout() {}\n"
        "}\n"
        "export function issueToken() {}\n"
    )
    assert "src/auth/service.ts::AuthService" in keys
    assert "src/auth/service.ts::AuthService.login" in keys
    assert "src/auth/service.ts::AuthService.logout" in keys
    assert "src/auth/service.ts::issueToken" in keys


def test_interface_type_enum_are_symbols():
    keys, _ = _keys(
        "export interface Session {}\n"
        "export type Id = string;\n"
        "export enum Role { Admin }\n"
    )
    assert "src/auth/service.ts::Session" in keys
    assert "src/auth/service.ts::Id" in keys
    assert "src/auth/service.ts::Role" in keys


def test_duplicate_overloads_get_discriminator():
    keys, result = _keys(
        "export function fmt(x: number): string;\n"
        "export function fmt(x: string): string;\n"
        "export function fmt(x: any): string { return String(x); }\n"
    )
    assert "src/auth/service.ts::fmt" in keys
    assert "src/auth/service.ts::fmt#2" in keys
    assert any(d.code == "RI-KEY-DUP-SYMBOL" for d in result.diagnostics)


def test_top_level_const_becomes_symbol_with_exported_flag():
    keys, result = _keys(
        "export const router = createBrowserRouter([]);\n"
        "const helper = 1;\n"
    )
    assert "src/auth/service.ts::router" in keys
    assert "src/auth/service.ts::helper" in keys
    router = next(n for n in result.nodes if n.stable_key == "src/auth/service.ts::router")
    assert router.properties is not None and router.properties.get("exported") is True
    helper = next(n for n in result.nodes if n.stable_key == "src/auth/service.ts::helper")
    assert helper.properties is None or helper.properties.get("exported") is not True


def test_exported_function_carries_exported_property():
    _, result = _keys("export function issueToken() {}\n")
    token = next(
        n for n in result.nodes if n.stable_key == "src/auth/service.ts::issueToken"
    )
    assert token.properties is not None and token.properties.get("exported") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_symbols.py -v`
Expected: FAIL — no symbol nodes yet.

- [ ] **Step 3: Add a cursor walk that collects named declarations**

In `apps/backend/app/extraction/typescript.py`, add imports:

```python
from app.extraction.base import ExtractedDiagnostic, ExtractedObservation, RI_KEY_DUP_SYMBOL
from app.extraction.naming import DiscriminatorAssigner, symbol_stable_key
```

Add a constant mapping declaration node types to the child field that holds the name:

```python
_NAMED_DECLARATIONS = {
    "function_declaration": "name",
    "function_signature": "name",              # ambient/overload signatures (no body)
    "generator_function_declaration": "name",
    "class_declaration": "name",
    "abstract_class_declaration": "name",
    "interface_declaration": "name",
    "type_alias_declaration": "name",
    "enum_declaration": "name",
    "method_definition": "name",               # emitted via the unified path, in class scope
}
```

Including `function_signature` is what makes overload signatures (`export function fmt(...): string;` with no body) each become an occurrence, so duplicates get `#2`/`#3` discriminators. Including `method_definition` is what fixes the class-method traversal: a method is reached with its enclosing class already on the scope stack, so the single emission path qualifies it as `Class.method` — no separate method branch is needed.

In `extract`, replace `_ = tree` with:

```python
        observations: list[ExtractedObservation] = []
        self._collect_symbols(
            tree.root_node, path, line_count, file_key, nodes, observations, diagnostics
        )
        return ExtractionResult(
            nodes=tuple(nodes),
            observations=tuple(observations),
            diagnostics=tuple(diagnostics),
        )
```

(remove the previous `return ExtractionResult(nodes=..., diagnostics=...)` line).

Add these methods to `TypeScriptExtractor`:

```python
    def _node_text(self, node, source: bytes) -> str:
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _is_exported(self, node) -> bool:
        return node.parent is not None and node.parent.type == "export_statement"

    def _is_top_level(self, node) -> bool:
        parent = node.parent
        if parent is None:
            return False
        if parent.type == "program":
            return True
        return (
            parent.type == "export_statement"
            and parent.parent is not None
            and parent.parent.type == "program"
        )

    def _collect_symbols(
        self, root, path, line_count, file_key, nodes, observations, diagnostics
    ) -> None:
        assigner = DiscriminatorAssigner()
        source = root.text  # bytes of the whole tree
        counter = {"n": 0}  # mutable box so the one running ordinal is shared

        def emit(name_node, decl_node, scope, exported):
            """Emit one symbol node + its definition observation; return the name."""
            name = self._node_text(name_node, source)
            base_key = symbol_stable_key(path, scope, name)
            final_key, duplicate = assigner.key(base_key)
            key = canonical.normalize_stable_key("symbol", final_key)
            # tree-sitter rows are 0-based; RFC spans are 1-based inclusive.
            ev, diag = build_evidence(
                path, decl_node.start_point[0] + 1, decl_node.end_point[0] + 1,
                line_count, producer=self.producer,
            )
            if ev is None:
                if diag is not None:
                    diagnostics.append(diag)
                return None
            counter["n"] += 1
            nodes.append(
                ExtractedNode(
                    node_kind="symbol", stable_key=key, name=name,
                    language="typescript", evidence=(ev,),
                    properties={"exported": True} if exported else None,
                )
            )
            observations.append(
                ExtractedObservation(
                    observed_kind="definition", subject_kind="symbol",
                    subject_key=key, referent_text=None, ordinal=counter["n"], evidence=ev,
                )
            )
            if duplicate:
                diagnostics.append(
                    ExtractedDiagnostic(
                        code=RI_KEY_DUP_SYMBOL, category="duplicate symbol",
                        severity="info",
                        message=f"duplicate symbol name resolved with a discriminator: {final_key}",
                        path=canonical.normalize_repo_path(path), subject=key,
                    )
                )
            return name

        def visit(node, scope):
            # Top-level const/let/var bindings become symbols (RFC §4.3). Their
            # initializer expressions are intentionally not descended into here;
            # route literals inside them are found by the separate route pass.
            if node.type == "lexical_declaration":
                if self._is_top_level(node):
                    exported = self._is_exported(node)
                    for declarator in node.named_children:
                        if declarator.type != "variable_declarator":
                            continue
                        name_node = declarator.child_by_field_name("name")
                        if name_node is not None and name_node.type == "identifier":
                            emit(name_node, declarator, scope, exported)
                return

            child_scope = scope
            field = _NAMED_DECLARATIONS.get(node.type)
            if field is not None:
                name_node = node.child_by_field_name(field)
                if name_node is not None:
                    # A method_definition arrives here with its enclosing class
                    # already in `scope`, so the unified path qualifies it as
                    # Class.method with no special-casing.
                    emitted = emit(name_node, node, scope, self._is_exported(node))
                    if emitted is not None:
                        child_scope = [*scope, emitted]

            for child in node.named_children:
                visit(child, child_scope)

        visit(root, [])
```

The single `emit` closure is the only place a definition observation is created, so its `counter["n"]` gives every observation a distinct, monotonic ordinal — no hard-coded values. Methods, nested functions, top-level consts, and overload signatures all flow through it.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_symbols.py -v`
Expected: PASS (all five tests: two-method traversal, interface/type/enum, overload discriminators, top-level const with the exported flag, and the exported-function property).

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/typescript.py apps/backend/tests/extraction/test_typescript_symbols.py
git commit -m "feat(extraction): TypeScript extractor emits qualified symbols and definitions"
```

---

### Task B3: TypeScript — import/export-from observations

**Files:**
- Modify: `apps/backend/app/extraction/typescript.py`
- Test: `apps/backend/tests/extraction/test_typescript_imports.py`

**Interfaces:**
- Produces: an `import` observation (`referent_text` = the module specifier) for each `import`/`export … from`. (The `exported` property on symbols is already emitted in Task B2.)

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_typescript_imports.py`:

```python
from app.extraction.typescript import TypeScriptExtractor

EXTRACTOR = TypeScriptExtractor()


def _extract(source: str):
    return EXTRACTOR.extract("src/auth/service.ts", source.encode("utf-8"))


def test_imports_become_observations():
    result = _extract(
        "import { issueToken } from './tokens';\n"
        "export { refresh } from './session';\n"
    )
    specifiers = sorted(
        o.referent_text for o in result.observations if o.observed_kind == "import"
    )
    assert specifiers == ["./session", "./tokens"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_imports.py -v`
Expected: FAIL — no import observations yet.

- [ ] **Step 3: Add import collection**

Add a `_collect_imports` called from `extract`. It walks the tree for `import_statement` and `export_statement` nodes that have a `source` field (a `string` node), emitting an `import` observation with `referent_text` set to the string literal's inner text (surrounding quotes stripped), `subject_kind="file"`, `subject_key=file_key`, a one-based span from `start_point`/`end_point`, and a running file-level ordinal that continues from the symbol observations.

Add to `extract` before the `return`:

```python
        self._collect_imports(tree.root_node, path, line_count, file_key, observations)
```

Add:

```python
    def _collect_imports(self, root, path, line_count, file_key, observations) -> None:
        source = root.text
        ordinal = len(observations)

        def walk(node):
            nonlocal ordinal
            if node.type in ("import_statement", "export_statement"):
                source_node = node.child_by_field_name("source")
                if source_node is not None:
                    literal = self._node_text(source_node, source).strip("'\"`")
                    ev, _ = build_evidence(
                        path, node.start_point[0] + 1, node.end_point[0] + 1,
                        line_count, producer=self.producer,
                    )
                    if ev is not None:
                        ordinal += 1
                        observations.append(
                            ExtractedObservation(
                                observed_kind="import", subject_kind="file",
                                subject_key=file_key, referent_text=literal,
                                ordinal=ordinal, evidence=ev,
                            )
                        )
            for child in node.named_children:
                walk(child)

        walk(root)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_imports.py tests/extraction/test_typescript_symbols.py -v`
Expected: PASS (both — B2's symbol/exported tests still pass, and imports are now observed).

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/typescript.py apps/backend/tests/extraction/test_typescript_imports.py
git commit -m "feat(extraction): TypeScript extractor emits import observations"
```

---

### Task B4: TypeScript — react-router route observations

**Files:**
- Modify: `apps/backend/app/extraction/typescript.py`
- Test: `apps/backend/tests/extraction/test_typescript_routes.py`

**Interfaces:**
- Produces: a `route` observation for each `createBrowserRouter` entry object with a `path` property and each JSX `<Route path="...">`; `referent_text` = the literal path string only.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_typescript_routes.py`:

```python
from app.extraction.typescript import TypeScriptExtractor

EXTRACTOR = TypeScriptExtractor()


def test_create_browser_router_paths_become_route_observations():
    source = (
        "import { createBrowserRouter } from 'react-router-dom';\n"
        "export const router = createBrowserRouter([\n"
        "  { path: '/login', element: null },\n"
        "  { path: '/dashboard', element: null },\n"
        "]);\n"
    )
    result = EXTRACTOR.extract("src/app/routes/router.ts", source.encode("utf-8"))
    paths = sorted(o.referent_text for o in result.observations if o.observed_kind == "route")
    assert paths == ["/dashboard", "/login"]


def test_jsx_route_path_becomes_route_observation():
    source = "const x = <Route path='/settings' />;\n"
    result = EXTRACTOR.extract("src/app/routes/tree.tsx", source.encode("utf-8"))
    paths = [o.referent_text for o in result.observations if o.observed_kind == "route"]
    assert paths == ["/settings"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_routes.py -v`
Expected: FAIL — no route observations.

- [ ] **Step 3: Add route detection**

Add a `_collect_routes(root, path, line_count, file_key, observations)` called from `extract`. Walk the tree:
- For a `pair` node whose `key` child text is `path` and whose `value` child is a string, and which sits inside a `createBrowserRouter` call argument, emit a `route` observation with the string literal (quotes stripped).
- For a JSX attribute (`jsx_attribute`) whose name is `path` on a `<Route>` element, emit the same.

Concretely:

```python
    def _collect_routes(self, root, path, line_count, file_key, observations) -> None:
        source = root.text
        ordinal = len(observations)

        def emit(node, literal):
            nonlocal ordinal
            ev, _ = build_evidence(
                path, node.start_point[0] + 1, node.end_point[0] + 1,
                line_count, producer=self.producer,
            )
            if ev is not None:
                ordinal += 1
                observations.append(
                    ExtractedObservation(
                        observed_kind="route", subject_kind="file",
                        subject_key=file_key, referent_text=literal,
                        ordinal=ordinal, evidence=ev,
                    )
                )

        def walk(node):
            if node.type == "pair":
                key = node.child_by_field_name("key")
                value = node.child_by_field_name("value")
                if (key is not None and value is not None
                        and self._node_text(key, source).strip("'\"") == "path"
                        and value.type in ("string",)):
                    emit(node, self._node_text(value, source).strip("'\"`"))
            elif node.type == "jsx_attribute":
                children = node.named_children
                if children and self._node_text(children[0], source) == "path" and len(children) > 1:
                    literal = self._node_text(children[1], source).strip("'\"{}`")
                    emit(node, literal)
            for child in node.named_children:
                walk(child)

        walk(root)
```

Call it from `extract` before the `return`:

```python
        self._collect_routes(tree.root_node, path, line_count, file_key, observations)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_routes.py -v`
Expected: PASS. (If the JSX case fails because `.ts` was used instead of `.tsx`, confirm the test uses a `.tsx` path so the tsx grammar parses JSX — it does.)

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/typescript.py apps/backend/tests/extraction/test_typescript_routes.py
git commit -m "feat(extraction): TypeScript extractor emits react-router route observations"
```

---

### Task B5: TypeScript — blind-spot diagnostics

**Files:**
- Modify: `apps/backend/app/extraction/typescript.py`
- Test: `apps/backend/tests/extraction/test_typescript_diagnostics.py`

**Interfaces:**
- Produces: `RI-EXT-UNSUPPORTED` (info) for dynamic `import(...)` calls, `namespace`/ambient `module` declarations, and CommonJS `require(...)` calls; `RI-SRC-MALFORMED` (error) when the parse tree has errors (`root_node.has_error`).

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_typescript_diagnostics.py`:

```python
from app.extraction.typescript import TypeScriptExtractor

EXTRACTOR = TypeScriptExtractor()


def _codes(source: str, path: str = "src/x.ts"):
    result = EXTRACTOR.extract(path, source.encode("utf-8"))
    return [d.code for d in result.diagnostics]


def test_dynamic_import_flagged():
    assert "RI-EXT-UNSUPPORTED" in _codes("const m = import('./x');\n")


def test_namespace_flagged():
    assert "RI-EXT-UNSUPPORTED" in _codes("namespace N { export const a = 1; }\n")


def test_commonjs_require_flagged():
    assert "RI-EXT-UNSUPPORTED" in _codes("const fs = require('fs');\n")


def test_parse_error_is_malformed():
    assert "RI-SRC-MALFORMED" in _codes("class {{{ broken\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_diagnostics.py -v`
Expected: FAIL — diagnostics not emitted.

- [ ] **Step 3: Add blind-spot + parse-error detection**

In `extract`, right after building `tree`, add a parse-error check:

```python
        if tree.root_node.has_error:
            diagnostics.append(
                ExtractedDiagnostic(
                    code="RI-SRC-MALFORMED", category="malformed source",
                    severity="error", message="file has TypeScript syntax errors",
                    path=canonical.normalize_repo_path(path),
                )
            )
```

Add `_collect_blind_spots(tree.root_node, path, line_count, diagnostics)` before the `return`, and:

```python
    def _collect_blind_spots(self, root, path, line_count, diagnostics) -> None:
        source = root.text
        normalized = canonical.normalize_repo_path(path)

        def flag(node, message):
            diagnostics.append(
                ExtractedDiagnostic(
                    code="RI-EXT-UNSUPPORTED", category="unsupported construct",
                    severity="info", message=message, path=normalized,
                    span=(node.start_point[0] + 1, node.end_point[0] + 1),
                )
            )

        def walk(node):
            if node.type in ("internal_module", "module") and node.child_by_field_name("name") is not None:
                flag(node, "namespace/module declaration is unsupported")
            elif node.type == "call_expression":
                fn = node.child_by_field_name("function")
                if fn is not None:
                    text = self._node_text(fn, source)
                    if fn.type == "import":
                        flag(node, "dynamic import() is unsupported")
                    elif text == "require":
                        flag(node, "CommonJS require() is unsupported")
            for child in node.named_children:
                walk(child)

        walk(root)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_diagnostics.py -v`
Expected: PASS. (If `namespace` matches a different node type in the installed grammar, run a one-off probe: `.venv/Scripts/python.exe -c "import tree_sitter_typescript as t; from tree_sitter import Language, Parser; p=Parser(Language(t.language_typescript())); print(p.parse(b'namespace N {}').root_node.named_children[0].type)"` and use the printed type in the `walk` check.)

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/typescript.py apps/backend/tests/extraction/test_typescript_diagnostics.py
git commit -m "feat(extraction): TypeScript extractor emits blind-spot diagnostics"
```

---

### Task B6: TypeScript support matrix entry + parity test

**Files:**
- Modify: `apps/backend/app/extraction/support_matrix.py`
- Modify: `apps/backend/tests/extraction/test_support_matrix.py`

**Interfaces:**
- Produces: `SUPPORT_MATRIX["typescript"]`.

- [ ] **Step 1: Write the failing test**

Append to `apps/backend/tests/extraction/test_support_matrix.py`:

```python
def test_typescript_matrix_lists_supported_and_unsupported():
    ts = SUPPORT_MATRIX["typescript"]
    for entry in ("file", "import", "export", "function", "class", "interface", "type", "enum", "route"):
        assert entry in ts.supported
    for entry in ("dynamic-import", "decorator", "namespace", "commonjs-require"):
        assert entry in ts.unsupported
    assert set(ts.supported).isdisjoint(ts.unsupported)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_support_matrix.py::test_typescript_matrix_lists_supported_and_unsupported -v`
Expected: FAIL — `KeyError: 'typescript'`.

- [ ] **Step 3: Add the TypeScript entry**

In `apps/backend/app/extraction/support_matrix.py`, add to the `SUPPORT_MATRIX` dict:

```python
    "typescript": LanguageSupport(
        supported=(
            "file", "import", "export", "function", "class", "method",
            "interface", "type", "enum", "const", "route",
        ),
        unsupported=("dynamic-import", "decorator", "namespace", "commonjs-require", "ambient-module"),
    ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_support_matrix.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/extraction/support_matrix.py apps/backend/tests/extraction/test_support_matrix.py
git commit -m "feat(extraction): publish TypeScript support matrix"
```

---

### Task B7: SnapshotStore integration — TypeScript facts seal

**Files:**
- Test: `apps/backend/tests/extraction/test_typescript_snapshot_integration.py`

**Interfaces:**
- Consumes: `TypeScriptExtractor`, `SnapshotStore` (#88), the fixture pattern from Task A11.
- Produces: proof a TS `ExtractionResult` seals to `completed`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/extraction/test_typescript_snapshot_integration.py`:

```python
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import register_sqlite_foreign_key_enforcement
from app.extraction.typescript import TypeScriptExtractor
from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
from app.models import RepositoryRecord, User
from app.models.base import Base

UPLOAD_REVISION = "sha256:" + "a" * 64


@pytest.fixture()
def session(tmp_path):
    register_sqlite_foreign_key_enforcement()
    engine = create_engine(f"sqlite:///{tmp_path / 'snap.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        yield db
    engine.dispose()


def _repository(session: Session) -> RepositoryRecord:
    owner = User(id=str(uuid4()), email="o@example.com", password_hash=None)
    session.add(owner)
    session.commit()
    record = RepositoryRecord(
        id=str(uuid4()), owner_id=owner.id, name="repo", source="upload",
        revision_kind="upload", revision_value=UPLOAD_REVISION,
        local_path="/x", status="completed", file_tree=[],
    )
    session.add(record)
    session.commit()
    return record


def _to_evidence(extracted) -> Evidence:
    return Evidence(
        path=extracted.path, start_line=extracted.start_line,
        end_line=extracted.end_line, extractor="typescript-ast",
        extractor_version="1.0.0", logical_line_count=extracted.logical_line_count,
        granularity=extracted.granularity,
    )


def test_typescript_extraction_result_seals_into_a_snapshot(session):
    repository = _repository(session)
    result = TypeScriptExtractor().extract(
        "src/auth/service.ts",
        b"export function issueToken() {\n  return 1;\n}\n",
    )
    store = SnapshotStore(session)
    snapshot = store.begin(
        repository_id=repository.id,
        revision=Revision("upload", UPLOAD_REVISION),
        producer_version_set=["typescript-ast@1.0.0"],
    )
    # a repo:root node is required for a coherent snapshot (RFC §11.2 rule 5)
    root_ev = Evidence(
        path="src/auth/service.ts", start_line=1, end_line=1,
        extractor="typescript-ast", extractor_version="1.0.0",
        logical_line_count=1, granularity="file",
    )
    store.add_node(snapshot, node_kind="repository", stable_key="repo:root", evidence=[root_ev])
    for node in result.nodes:
        store.add_node(
            snapshot, node_kind=node.node_kind, stable_key=node.stable_key,
            name=node.name, language=node.language,
            properties=node.properties,
            evidence=[_to_evidence(e) for e in node.evidence],
        )
    for obs in result.observations:
        store.add_observation(
            snapshot, observed_kind=obs.observed_kind, subject_kind=obs.subject_kind,
            subject_key=obs.subject_key, referent_text=obs.referent_text,
            ordinal=obs.ordinal, evidence=_to_evidence(obs.evidence),
        )
    for diag in result.diagnostics:
        store.add_diagnostic(
            snapshot, code=diag.code, category=diag.category, severity=diag.severity,
            message=diag.message, producer="typescript-ast@1.0.0", path=diag.path,
            span=diag.span, subject=diag.subject, details=diag.details,
        )

    sealed = store.seal(snapshot)
    assert sealed.state == "completed"
    assert sealed.canonical_graph_hash.startswith("sha256:")
```

- [ ] **Step 2: Run and verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/test_typescript_snapshot_integration.py -v`
Expected: PASS (wires existing pieces; if it fails, the failure names the contract gap to fix in `typescript.py`, same as Task A11 Step 3).

- [ ] **Step 3: Confirm the whole extraction suite is green**

Run: `.venv/Scripts/python.exe -m pytest tests/extraction/ -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/backend/tests/extraction/test_typescript_snapshot_integration.py
git commit -m "test(extraction): prove TypeScript extraction seals into a snapshot"
```

---

## Phase C — Remove the placeholder

### Task C1: Delete `TreeSitterParser`, decouple `engine.py`

**Files:**
- Delete: `apps/backend/app/parsers/tree_sitter_parser.py`
- Modify: `apps/backend/app/intelligence/engine.py`
- Test: `apps/backend/tests/test_repository_intelligence.py` (confirm existing behavior)

**Interfaces:**
- Consumes: nothing new.
- Produces: `engine.py` no longer imports `TreeSitterParser`; its regex extraction for non-TS/Python files is unchanged.

- [ ] **Step 1: Confirm the placeholder's only consumer**

Run: `.venv/Scripts/python.exe -m pytest tests/test_repository_intelligence.py -v`
Expected: PASS (baseline). Then search usages:
```bash
grep -rn "tree_sitter_parser\|TreeSitterParser\|syntax_parser\|parse_symbols" apps/backend/app
```
Expected: matches only in `engine.py` and the file being deleted.

- [ ] **Step 2: Remove the parser usage from `engine.py`**

In `apps/backend/app/intelligence/engine.py`:
- Delete the import line `from app.parsers.tree_sitter_parser import TreeSitterParser`.
- In `RepositoryIntelligenceEngine.__init__`, remove the `syntax_parser` parameter and the `self.syntax_parser = ...` line.
- In `_file_intelligence`, delete the two lines that call `self.syntax_parser.parse_symbols(...)` and the `if syntax.language and not language:` block that overrode `language` from it. `language` already comes from `node.language`; leave the rest of the method intact.

- [ ] **Step 3: Delete the placeholder file**

```bash
git rm apps/backend/app/parsers/tree_sitter_parser.py
```

- [ ] **Step 4: Run tests to verify no regression**

Run: `.venv/Scripts/python.exe -m pytest tests/test_repository_intelligence.py tests/test_ingestion_pipeline.py -v`
Expected: PASS. The legacy regex intelligence blob is unchanged for non-TS/Python files; the engine simply no longer references the dead placeholder.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/intelligence/engine.py apps/backend/app/parsers/tree_sitter_parser.py
git commit -m "refactor(extraction): remove TreeSitterParser placeholder from engine"
```

---

## Final verification (before opening the PR)

- [ ] Run the full backend suite from `apps/backend`: `.venv/Scripts/python.exe -m pytest`
  Expected: all pass (existing suite + new `tests/extraction/`).
- [ ] Confirm no live wiring crept in: `grep -rn "PythonExtractor\|TypeScriptExtractor" apps/backend/app` should show references only inside `app/extraction/`, not in `services/`, `api/`, or `engine.py`.
- [ ] Push the branch and open a PR targeting `dev` that closes #89 and #90.

## Open the PR

```bash
git push -u origin feat/89-90-evidence-extractors
gh pr create --base dev --title "feat(extraction): evidence-backed TypeScript and Python extractors (#89, #90)" --body "Implements #89 and #90 per docs/superpowers/specs/2026-07-16-evidence-extractors-design.md. Closes #89. Closes #90."
```
