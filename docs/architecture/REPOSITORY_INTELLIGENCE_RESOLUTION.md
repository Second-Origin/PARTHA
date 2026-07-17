# Repository Intelligence relationship resolution

This document defines the deterministic resolver introduced for Issue #91. It
applies only to facts already stored in a **building** `ri.v1` snapshot. A
resolver never reads the repository working tree, reparses a source file, or
creates an `observed` node or edge.

## Inputs and outcomes

Extractors and manifest readers store observations with exact source evidence.
The resolver sorts those observations by `observation_id`, builds candidate
indexes from the snapshot's nodes, and applies the rules below. Every attempted
relationship has one of three outcomes:

| Candidate count | Output |
| --- | --- |
| one | One `resolved` edge with resolver evidence at the observation span and a `derived_from` observation reference. |
| zero | `RI-RES-UNRESOLVED` warning with the observation id. No edge. |
| more than one | `RI-RES-AMBIGUOUS` warning with sorted candidate stable keys. No edge. |

Warnings remain in a completed snapshot. They are part of the canonical graph
hash and make missing knowledge visible; they are never replaced by a guessed
edge.

## Stored observation contract

| Observation | Extracted input | Resolved predicate |
| --- | --- | --- |
| `definition` | Symbol definition | `contains`, `defines` |
| `import` | Module specifier | `imports` |
| `import_binding` | `specifier|imported|local` exact binding representation | supports `imports`, `calls`, `implements`, `routes_to` lookup |
| `call` | Direct named call | `calls` |
| `implements` | TypeScript `implements` clause | `implements` |
| `route` + `route_handler` | Route declaration and one handler reference | `routes_to` |
| `dependency` | Direct manifest declaration on a dependency node | `depends_on` |

`import_binding` uses an unambiguous delimiter format because `ri.v1`
observations intentionally have only `referent_text`; it is still direct
extractor output, not resolver-generated source interpretation.

## Algorithms

### Structural edges

For each `definition` observation, split the symbol stable key at `::`. A
nested qualified name resolves to its immediate enclosing symbol only if that
symbol exists in the snapshot. A top-level name resolves to `file:<path>` only
if that file node exists. Emit both `contains` and `defines` edges from that
single parent to the definition symbol.

### Imports and dependencies

For a relative TypeScript/Python specifier, generate the complete candidate set
without precedence: explicit extensions plus `.ts`, `.tsx`, `.py`, TypeScript
`index.*`, and Python `__init__.py` forms. Relative Python dotted imports also
consider each stored module prefix, which preserves the existing extractor
representation for `from .pkg import symbol`.

An absolute Python `from a.b import c` is stored as the import referent `a.b.c`,
whose module is `a.b`. Because `c` may be either a submodule (`a/b/c.py`) or a
member of the module `a/b.py`, the resolver derives module-file candidates from
both the full referent and the stored `import_binding` module specifier `a.b`,
using the binding rather than reparsing source. Match candidates only against
stored file nodes; when any local file node matches, an external dependency
with the same package root is never substituted.

For a bare specifier with no matching local file node, derive its npm package
root (including scoped packages) or PEP 503-normalized PyPI root and match only
an already-stored dependency node. No `external:*` placeholder is created. A
`dependency` observation resolves `repo:root -> dependency` as `depends_on`.
Genuinely ambiguous module layouts stay ambiguous; unresolved ones stay
diagnostics.

### References and implementations

A relationship is emitted only when a stored syntax fact uniquely proves it.
Evidence is considered in a fixed order: a direct stable-key referent, then a
same-file top-level symbol, then the explicit `import_binding` records for the
source file. There is **no** repository-wide same-name fallback. Without a
same-file definition or an import binding, a lone symbol elsewhere that happens
to share the name is not proof and stays unresolved. When a binding exists but
its module or exported symbol cannot be resolved, the reference stays
unresolved rather than borrowing an unrelated same-named symbol; when a binding
resolves to more than one target, it stays ambiguous. This applies identically
to `calls`, `implements`, and `routes_to`. TypeScript extraction emits
`implements` only for direct `class ... implements ...` syntax; `extends` is
intentionally not repurposed as an `implements` fact.

### Routes

Extractors create an observed anonymous route symbol for each literal route
declaration. A `route_handler` observation must name exactly one direct handler
reference for the route. Python decorators bind the route to their decorated
function. TypeScript records static `Component`, `component`, and JSX `element`
references. Lazy, computed, or otherwise unsupported route handlers remain
unresolved rather than being inferred from a path.

## Truth classes and provenance

The resolver emits only `resolved` edges through `SnapshotStore.add_edge`. Each
edge has `relationship-resolver@1.0.0` as its immediate producer, carries the
same repository-relative span as its source observation under that resolver
producer identity, and has a tagged observation derivation. The producer must
be present in the snapshot's planned `producer_version_set`, which sealing
validates. Extractors remain the only producers of `observed` facts.

## Verification

The focused resolver tests cover successful structural/import/call/route/
dependency/implements edges, unresolved imports, actual TypeScript alias
resolution, and FastAPI decorator routes. They also prove the no-fallback rule:
a call, an imported route handler, and an implemented interface each stay
unresolved when only an unrelated repository-wide same-name symbol exists or
when an import binding is broken, while a binding that resolves to several
targets stays ambiguous. A dedicated case shows an absolute `from a.b import c`
resolving its import edge to the module file `a/b.py` even when a same-named
dependency is present. All warning paths are sealed successfully to prove that
honest partial knowledge remains usable.
