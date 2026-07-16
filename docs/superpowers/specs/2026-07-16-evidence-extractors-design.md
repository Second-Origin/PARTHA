# Design — Evidence-backed TypeScript & Python extractors (#89, #90)

| | |
| --- | --- |
| **Issues** | [#89](https://github.com/Second-Origin/PARTHA/issues/89) (TypeScript), [#90](https://github.com/Second-Origin/PARTHA/issues/90) (Python) |
| **Governing contract** | RFC-0001 (Repository Intelligence v1), **Accepted** 2026-07-16 |
| **Depends on** | #88 immutable snapshot persistence (`SnapshotStore`, `Evidence`, `ri_*` tables) — merged to `dev` in PR #102 |
| **Status** | Design — pending maintainer approval |

## 1. Goal and scope

Replace regex symbol extraction (for TypeScript and Python only) with two real,
evidence-backed extractors that emit RFC-0001 `observed` facts — nodes and
observations, each carrying a valid line span — against a **named support
matrix**. Constructs outside the matrix produce diagnostics, never silent drops
and never invented facts.

### In scope

- A shared `Extractor` protocol and shared result/identity/diagnostic types in a
  new `apps/backend/app/extraction/` package.
- `TypeScriptExtractor` (`.ts`/`.tsx`) built on tree-sitter.
- `PythonExtractor` (`.py`) built on the standard-library `ast` module.
- A published support matrix per language (the deliverable, not just prose).
- Golden fixtures per supported construct and adversarial fixtures per declared
  blind spot.
- Integration tests that feed extractor output into `SnapshotStore` and seal a
  snapshot, proving the facts satisfy the persistence contract end to end.
- Removal of the `TreeSitterParser` placeholder.
- New pinned dependency: `tree-sitter-typescript` (grammar), plus regenerated
  `requirements.txt`.

### Explicitly out of scope

- **Resolution into edges.** Extractors emit `observed` nodes and `observation`
  records only. Turning an import/call/route observation into a `resolved` edge
  is #91's job (RFC §7.2 emission matrix: an extractor MUST NOT emit `resolved`).
- **Live wiring into import/analysis.** The extractors are not called from
  `POST /repositories/*` or `/analysis/{id}/start`. Production wiring waits for
  #93 (durable job lifecycle), which replaces today's synchronous analysis; wiring
  now would be rewritten then.
- **JavaScript (`.js`/`.jsx`).** Out of the `ri.v1` support matrix for these
  issues; the legacy regex path in `engine.py` continues to serve the non-`ri.v1`
  blob for those files unchanged.
- **Other languages.** Per the RFC's breadth-before-depth rule: no third language
  until TS and Python both meet the support contract.
- **The legacy `engine.py` blob.** Its regex output stays as `legacy_unverified`
  compatibility data (RFC §10.3). These extractors do not feed it and do not
  replace its non-TS/Python behavior.

## 2. The extractor/resolver boundary (the load-bearing decision)

RFC §2.2 and §7.2 draw a hard line: an **extractor** reads a source span and emits
`observed` facts; a **resolver** (#91) reads stored observations and emits
`resolved` edges. #89/#90 are extractors, so they do **not** emit edges.

Concretely, for each cross-reference the extractor records an **observation**
(RFC §6.4) — an evidence-bearing record of the raw syntax — and leaves resolution
to #91:

- An `import './tokens'` becomes an `observation` with `observed_kind: "import"`,
  `referent_text: "./tokens"`, evidence at the import line. It does **not** become
  an edge to `file:src/auth/tokens.ts`.
- A FastAPI `@router.post("/login")` under `router = APIRouter(prefix="/auth")`
  becomes an `observation` with `observed_kind: "route"`,
  `referent_text: "/login"` — the **literal decorator string only**. Joining the
  `/auth` prefix to produce the effective path `/auth/login` requires binding
  `router` across two statements: that is cross-statement inference, a resolver's
  job, not an extractor's. The extractor never emits `/auth/login`.

This keeps #89/#90 independently correct and testable, and means #91 has real
observations to resolve rather than having to re-parse source.

## 3. Parser strategy

**Python → standard-library `ast`. TypeScript → tree-sitter.** Not tree-sitter
for both.

- **Python `ast`** is native (no grammar dependency), always spec-correct for the
  interpreter (repo floor is Python 3.12), and gives exact spans via `lineno` /
  `end_lineno` (stable since 3.8). Qualified names fall out of an `ast.NodeVisitor`
  scope stack; decorators are `node.decorator_list` directly — which #90 leans on
  for FastAPI routes. Its fail-hard behavior on a syntax error is *correct* for an
  evidence contract: a `SyntaxError` becomes an `RI-SRC-MALFORMED` diagnostic
  (RFC §8.2), not partial extraction. Tree-sitter's error-tolerant recovery would
  be a liability here.
- **TypeScript tree-sitter**: there is no native TypeScript parser in Python.
  tree-sitter runs in-process (no Node runtime, no subprocess), which the security
  model prefers. Construct discovery uses tree-sitter **queries** (`.scm`
  patterns) — one named query per supported construct, so the query set *is* the
  machine-checkable support matrix. Qualified names come from walking each match's
  `.parent` chain to reconstruct enclosing scope, which queries alone cannot give.

**Shared interface is preserved** (#90 acceptance criterion): both extractors
implement one `Extractor` protocol and return the same `ExtractionResult`
dataclasses; the qualified-name builder, source-order discriminator assignment
(RFC §4.3), path normalization, and diagnostic emission live once in `base.py`.
Only the parser *backend* differs — appropriately, because the languages differ
and Python has a native parser TypeScript lacks. "Shared interface, not a parallel
implementation" is satisfied at the interface, not by forcing one parser library.

## 4. Package layout

```
apps/backend/app/extraction/
  __init__.py           # exports Extractor, ExtractionResult, extractor_for()
  base.py               # Extractor protocol; result/observation/diagnostic types;
                        # qualified-name + discriminator + path-normalization helpers;
                        # logical-line-count + span validation; diagnostic codes
  typescript.py         # TypeScriptExtractor (tree-sitter)
  queries/              # *.scm tree-sitter queries, one per supported construct
  python.py             # PythonExtractor (ast.NodeVisitor)
  support_matrix.py     # the published matrix, asserted by both docs and tests
apps/backend/app/parsers/tree_sitter_parser.py   # DELETED
apps/backend/tests/extraction/
  fixtures/typescript/  # one source file per supported construct + per blind spot
  fixtures/python/
  test_typescript_extractor.py
  test_python_extractor.py
  test_extractor_snapshot_integration.py          # ExtractionResult -> SnapshotStore -> seal
  test_support_matrix.py                           # matrix <-> implementation parity
```

`engine.py` stops calling `TreeSitterParser`; its regex symbol extraction remains
for non-TS/Python files feeding the legacy blob, untouched.

## 5. Data model (`base.py`)

Plain frozen dataclasses, decoupled from the ORM (so extractors stay unit-testable
and #93 can later drive them into `SnapshotStore` from a job):

```python
@dataclass(frozen=True)
class ExtractedEvidence:
    path: str            # repo-relative POSIX, normalized (RFC §4.2)
    start_line: int      # one-based
    end_line: int        # one-based inclusive
    logical_line_count: int
    granularity: str = "span"          # "span" | "file"

@dataclass(frozen=True)
class ExtractedNode:
    node_kind: str       # "file" | "module" | "symbol" | "dependency"
    stable_key: str      # normalized per RFC §4.3
    name: str | None
    language: str | None
    evidence: tuple[ExtractedEvidence, ...]
    properties: Mapping[str, object] | None = None

@dataclass(frozen=True)
class ExtractedObservation:
    observed_kind: str   # "definition" | "import" | "call" | "route" | ...
    subject_kind: str
    subject_key: str
    referent_text: str | None
    ordinal: int
    evidence: ExtractedEvidence

@dataclass(frozen=True)
class ExtractedDiagnostic:
    code: str            # RI-EXT-UNSUPPORTED, RI-SRC-MALFORMED, ...
    category: str
    severity: str        # fatal | error | warning | info
    message: str         # deterministic: no timestamps/absolute paths
    path: str | None = None
    span: tuple[int, int] | None = None
    subject: str | None = None
    details: Mapping[str, object] | None = None

@dataclass(frozen=True)
class ExtractionResult:
    nodes: tuple[ExtractedNode, ...]
    observations: tuple[ExtractedObservation, ...]
    diagnostics: tuple[ExtractedDiagnostic, ...]

class Extractor(Protocol):
    name: str            # "typescript-ast" | "python-ast"
    version: str         # "1.0.0"
    def supports(self, path: str) -> bool: ...
    def extract(self, path: str, source: bytes) -> ExtractionResult: ...
```

These map one-to-one onto `SnapshotStore.add_node` / `add_observation` /
`add_diagnostic` and the `Evidence` value object from #88. The extractor takes
raw `bytes` (not decoded text) so it owns the UTF-8 decode and can emit
`RI-SRC-BINARY` / `RI-SRC-MALFORMED` itself (RFC §6.2). `producer` on the
resulting `Evidence` is `f"{extractor.name}@{extractor.version}"`.

## 6. Support matrix (draft — refined during implementation, published as the deliverable)

`support_matrix.py` is the single source; docs and `test_support_matrix.py` both
assert against it so they cannot drift.

### TypeScript (`.ts`, `.tsx`)

| Supported → node/observation | Not supported → diagnostic |
| --- | --- |
| file node (whole-file evidence) | dynamic `import()` → `RI-EXT-UNSUPPORTED` |
| module node (`mod:<dir>`, directory-scoped, language-neutral) | decorators → `RI-EXT-UNSUPPORTED` |
| `import`/`export … from` → `import` observation | `namespace` / ambient `module` → `RI-EXT-UNSUPPORTED` |
| function decls (incl. nested, arrow assigned to const) → symbol node + `definition` obs | `export =` / `require(...)` (CommonJS) → `RI-EXT-UNSUPPORTED` |
| class decls + methods (incl. nested) → symbol nodes | |
| `interface` / `type` / `enum` / exported `const` → symbol nodes | |
| react-router routes (`<Route path=…>`, router-factory route tables) → `route` obs | |

> **Exports** (an explicit #89 deliverable) are represented as an `exported: true`
> **node property** on the symbol they qualify — not a separate node kind. A
> re-export (`export … from`) is additionally an `import` observation, since it is
> a cross-file reference a resolver will later follow.
>
> Route detection matches this repo's actual routing (`createBrowserRouter` in
> `apps/frontend/src/app/routes/router.tsx`), not generic Express `.get('/x')`
> calls the old regex looked for and never found here.
>
> **Decorators are unsupported for TypeScript but supported for Python** — this is
> not an oversight: it traces directly to each issue's own scope. #89 lists
> files/modules/symbols/imports/exports/routes (no decorators); #90 lists
> modules/classes/functions/imports/routes/**decorators**. TS decorators are a
> more complex stage-3 feature with metadata semantics; Python decorators are
> first-class via `ast.decorator_list`.

### Python (`.py`)

| Supported → node/observation | Not supported → diagnostic |
| --- | --- |
| module node (`mod:<dir>`, directory-scoped, language-neutral) | `import *` (star-import) → `RI-EXT-UNSUPPORTED` |
| `import` / `from … import` → `import` observation | dynamic import (`import_module`, bare or via `importlib`; `__import__`) → `RI-EXT-UNSUPPORTED` |
| function defs (incl. nested, async) → symbol node + `definition` obs | reflection (`getattr`/`setattr`/`delattr`) → `RI-EXT-UNSUPPORTED` |
| class defs + methods (incl. nested) → symbol nodes | monkey-patching (rebinding an attribute on an imported name) → `RI-EXT-UNSUPPORTED` |
| decorators → `decorator` observation (own span) + node property | metaclasses → `RI-EXT-UNSUPPORTED` |
| FastAPI route decorators → `route` obs (literal path only) | syntax error → `RI-SRC-MALFORMED` (whole file, no facts) |

## 7. Stable keys, qualified names, spans (shared, `base.py`)

- **Stable keys** per RFC §4.3: `file:<path>`, `mod:<dir>`,
  `<path>::<qualified.name>[#<n>]`, `dep:<ecosystem>:<name>`. Paths normalized per
  §4.2 (POSIX, lexical `.`/`..` resolution, reject escapes → `RI-SEC-PATH-ESCAPE`,
  NFC). Symbol keys carry no `sym:` prefix (detected by `::`).
- **Qualified names**: dotted enclosing-scope path, language-native.
  `AuthService.login`, `outer._inner`. Python from the `NodeVisitor` scope stack;
  TypeScript from the parent-walk.
- **Discriminators** (RFC §4.3, revision-local, source-order): duplicate
  `<path>::<qualified-name>` gets `#2`, `#3`… by ascending start position (first
  has none) + an informational `RI-KEY-DUP-SYMBOL`. Anonymous symbols that must be
  represented get `(anonymous:<kind>#<ordinal>)`.
- **Spans** (RFC §6.2): one-based, inclusive; `logical_line_count = 1 +
  count(U+000A)` over the strict UTF-8 decode; empty file = 1 logical line;
  whole-file facts use `granularity: "file"`, `1..logical_line_count`. A span
  outside `1 ≤ start ≤ end ≤ logical_line_count` is dropped with `RI-SPAN-INVALID`
  rather than stored.

## 8. Diagnostics behavior

Diagnostics are **opt-in per declared blind spot**, driven by explicit queries /
AST checks — there is no generic "unmatched node" fallback (which would flag
comments and punctuation as gaps). Severities follow RFC §8.3–8.4: the extractors
emit only non-fatal diagnostics (`RI-EXT-UNSUPPORTED` = info, `RI-SRC-BINARY` =
info, `RI-SRC-MALFORMED` = error, `RI-SPAN-INVALID` = error, `RI-KEY-DUP-SYMBOL` =
info). A snapshot with only these still seals `completed` with visible gaps —
extractors never produce `fatal`.

## 9. Testing

- **Golden fixtures** — one minimal source file per supported construct, asserting
  exact nodes/observations with exact stable keys and spans (mirrors the existing
  `test_canonical_hash.py` vector style). Includes the RFC §6.2 empty-file and
  `\r\n` line-count vectors.
- **Adversarial fixtures** — one per declared blind spot, asserting the specific
  diagnostic code fires and no fact is fabricated; plus a syntax-error file
  (`RI-SRC-MALFORMED`) and a NUL-byte file (`RI-SRC-BINARY`).
- **Support-matrix parity** — `test_support_matrix.py` asserts every matrix entry
  has a fixture and vice-versa, so the published matrix cannot lie.
- **SnapshotStore integration** — feed a fixture's `ExtractionResult` through
  `SnapshotStore.add_node/add_observation/add_diagnostic` and `seal()`, proving the
  facts satisfy #88's persistence contract and that a real snapshot completes
  end to end (this is where "every emitted fact carries valid provenance" is
  proven, per each issue's acceptance criteria).
- CI green (backend suite + lint).

## 10. Dependencies

- Add `tree-sitter-typescript` (grammar) to `apps/backend/pyproject.toml`; the
  base `tree-sitter==0.26.0` is already pinned. Regenerate `requirements.txt`.
- No `tree-sitter-python` — Python uses stdlib `ast`.
- No new frontend or runtime-service dependency.

## 11. Sequencing of the two issues

Land the shared `base.py` + one extractor first (Python, since `ast` is the lower-
risk backend and validates the interface), then the TypeScript extractor against
the same interface. Both can be one PR or two stacked PRs; the shared interface is
settled before the second extractor starts, satisfying #90's "shared interface"
criterion by construction.

## 12. Acceptance-criteria trace

| Criterion (#89/#90) | Satisfied by |
| --- | --- |
| Named support matrix published | §6, `support_matrix.py`, `test_support_matrix.py` |
| Files/modules/symbols/imports/exports/routes (TS) and modules/classes/functions/imports/routes/decorators (Py) with valid spans | §5–§7, golden fixtures |
| Every fact carries evidence conforming to the contract | §5, §7, SnapshotStore integration test |
| Golden fixtures per supported construct | §9 |
| Unsupported constructs & failures → diagnostics, not drops/guesses | §8, adversarial fixtures |
| `TreeSitterParser` made real or removed | §4 — removed |
| Shared extractor interface, not parallel impl (#90) | §3, §5 — shared `base.py` |
| CI green | §9 |
