# Repository Intelligence golden benchmark (Issue #94)

A deterministic, auditable benchmark that measures the Repository Intelligence
extractors against **independently authored** golden facts: extraction precision
and recall, citation/provenance validity, and snapshot-hash determinism. It is
the regression guard that answers "is the repository model actually correct?",
which a green test suite alone cannot.

The default runner sends every applicable fixture's stored bytes through the
production source-policy pipeline and the merged Python and TypeScript
extractors. It compares only real emitted nodes, observations, and diagnostics
with the independently authored golden facts; it never copies expected output
into the actual side.

## Where things live

| Path | What it is |
| --- | --- |
| [`fixtures/{minimal,realistic,adversarial}/`](fixtures) | The versioned golden corpus: synthetic source + a `manifest.json` of expected facts per fixture. |
| [`config/benchmark_support_matrix.json`](config/benchmark_support_matrix.json) | The benchmark construct taxonomy and validated mapping to every production support-matrix entry. |
| [`config/thresholds.json`](config/thresholds.json) | The versioned, exact-fraction acceptance thresholds. |
| [`facts.py`](facts.py) / [`scorer.py`](scorer.py) | The fact model and precision/recall scorer. |
| [`loader.py`](loader.py) / [`schema.py`](schema.py) | Strict manifest loading and validation. |
| [`provenance.py`](provenance.py) | Citation validity against the stored revision (RFC-0001 §6.2). |
| [`determinism.py`](determinism.py) | Repeated real extraction persisted through `SnapshotStore`, with canonical-hash determinism. |
| [`adapter.py`](adapter.py) | Exact conversion from real extractor results to comparable benchmark facts. |
| [`runner.py`](runner.py) / [`report.py`](report.py) / [`run.py`](run.py) | Orchestration, gating, and Markdown/JSON reports. |

## Running it locally

From `apps/backend` (with the backend venv active):

```bash
# Fast unit + integration guards (scorer, loader, provenance, determinism, failure paths):
python -m pytest tests/benchmark

# The full benchmark command with human/machine reports (writes to a throwaway dir):
python tests/benchmark/run.py --report-dir /tmp/ri-benchmark
cat /tmp/ri-benchmark/benchmark.md
```

The runner exits non-zero when any enforced gate fails. **Reports are generated,
never committed** (`.gitignore` excludes them; CI writes them to `$RUNNER_TEMP`).

## Fixture schema and versioning

Every fixture is a directory containing synthetic source files and a
`manifest.json` with `schemaVersion: "ri-benchmark.v1"`. Bumping that version is a
deliberate, reviewed migration (constants live in [`schema.py`](schema.py)). Each
manifest declares its `fixtureId`, `fixtureClass` (`minimal` / `realistic` /
`adversarial`), `language`, `revisionIdentity` (`upload-sha256`, a content hash of
the fixture bytes — never a fabricated Git SHA), `producerVersionSet`,
`constructsCovered`, and an `expected` block of nodes / edges / observations /
assertions / diagnostics. Each expected fact carries its normalized evidence
(path + one-based inclusive line span + granularity + extractor).

`syntheticFiles` is an optional manifest map of raw path to UTF-8 content. It is
part of the deterministic stored-revision byte map, but does not require the raw
path to exist on the host filesystem. This is reserved for source-policy cases
such as a Windows-invalid escaping path; it is not a golden-output generator.

The loader (`loader.py`) fails clearly on unsupported schema versions, duplicate
fixture ids, duplicate expected identities, missing source files, absolute or
`..`-escaping paths, invalid line ranges, undeclared construct ids, malformed
facts, unsupported languages, inconsistent producer versions, facts missing
mandatory evidence, and machine-blessed output.

## Metrics and thresholds

Comparison is by each fact's exact semantic identity (fact type, kind,
subject/object/predicate, node name/language, and the full normalized evidence
span set) — a node with the correct stable key but the wrong name or language
does **not** match, nor does a fact with the wrong line span. Matching is also
scoped by fixture id, so fixture-relative paths can safely repeat across the
corpus.

```
precision = TP / (TP + FP)          (= 1 when TP + FP = 0, i.e. nothing emitted)
recall    = TP / (TP + FN)          (= 1 when TP + FN = 0, i.e. nothing expected)
```

Counting is multiset-aware, so a duplicate emission is one TP and one FP. The
thresholds (`config/thresholds.json`) are the enforced acceptance bar from Issue
#94:

| Metric | Threshold | Enforced today? |
| --- | --- | --- |
| precision | ≥ 0.95 | **yes** |
| recall | ≥ 0.95 | **yes** |
| provenance validity | = 1.00 | **yes** |
| determinism | = 1.00 | **yes** |

Do **not** lower a threshold without documenting the reason on Issue #94 and
getting maintainer agreement.

## How unsupported constructs are scored

A construct outside the support matrix must produce **no fact** plus a specific
diagnostic (e.g. `RI-EXT-UNSUPPORTED`, `RI-SRC-MALFORMED`). In scoring:

- an invented fact where none is expected is a **false positive**;
- a missing required diagnostic is a **benchmark failure** (the runner checks that
  every unsupported construct has a fixture emitting its required diagnostic);
- unsupported constructs are never quietly dropped from the corpus.

## Adding or reviewing a fixture

1. Write small, original synthetic source (no third-party/copyrighted code).
2. Derive the expected facts **by hand** from the source and the support matrix —
   count the one-based line spans yourself. Do **not** run any extractor and copy
   its output.
3. Add the manifest; tag each fact with the support-matrix construct(s) it covers.
4. `python -m pytest tests/benchmark` — the loader validates structure and
   provenance; the runner validates parity, diagnostics, and determinism.

**There is deliberately no "bless/update snapshots" command.** Golden truth is
reviewed by a human, and a manifest carrying a `blessed`/`generated` marker is
rejected on load. A regeneration helper may only *format or validate* facts a
reviewer has already written.

## CI

The `Backend` job runs `python -m pytest` (which includes every benchmark
invariant and failure-path test) and then a dedicated step runs
`tests/benchmark/run.py`, uploads `benchmark.md` / `benchmark.json` as the
`ri-golden-benchmark` artifact (even on failure), writes a summary to the job
page, and fails the job when the benchmark is below threshold.

## What #94 proves

- the golden corpus is internally valid and every golden citation resolves to
  the stored revision;
- the real extractor output meets the configured precision and recall gates;
- every citation emitted by the real extractors is valid;
- repeated real extraction, including reversed insertion order, seals to the
  same product canonical graph hash;
- support-matrix drift, duplicate/cross-fixture facts, invalid citations, bad
  precision/recall, and nondeterminism fail the build.

This benchmark does not claim the legacy product ingestion path has migrated to
the normalized snapshot graph. That orchestration and consumer cutover remain
separate work; see
[`docs/architecture/REPOSITORY_INTELLIGENCE.md`](../../../../docs/architecture/REPOSITORY_INTELLIGENCE.md).
