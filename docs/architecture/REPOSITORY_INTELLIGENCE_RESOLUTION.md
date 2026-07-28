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
| `call_shadowed` | The paired call-site name is lexically local to its function/class scope | forces the paired `call` to an unresolved diagnostic |
| `implements` | TypeScript `implements` clause | `implements` |
| `route` + `route_handler` | Route declaration and one handler reference | `routes_to` |
| `dependency` | Direct manifest declaration on a dependency node | `depends_on` |
| `injects` | A `Depends(name)` argument (#95) | `injects` |
| `http_call` | A proven outbound HTTP call site, `METHOD\|origin\|path` (#209) | `calls_service` |
| `iac_resource` | A declared infrastructure resource on an `iac_resource` node (#209) | `declares` |
| `resolution` | A lockfile pin on a dependency node (#209) | *(none — deliberately not a relationship input)* |

`import_binding` uses an unambiguous delimiter format because `ri.v1`
observations intentionally have only `referent_text`; it is still direct
extractor output, not resolver-generated source interpretation.

Python `import_binding` is emitted only for a direct module-level import. A
function- or block-local import still produces an `import` observation, but it
cannot be exposed as a file-wide name binding. Calls through such local names
carry `call_shadowed` and fail closed until scope-qualified import bindings are
part of the stored contract.

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
source file. Before lookup, a paired `call_shadowed` observation forces the
call to remain unresolved; a parameter, function-local import, or local
declaration can therefore never borrow a same-named global/imported symbol.
There is **no** repository-wide same-name fallback. Without a
same-file definition or an import binding, a lone symbol elsewhere that happens
to share the name is not proof and stays unresolved. When a binding exists but
its module or exported symbol cannot be resolved, the reference stays
unresolved rather than borrowing an unrelated same-named symbol; when a binding
resolves to more than one target, it stays ambiguous. A default import resolves
only to a symbol carrying an explicit stored `default_export` property; the
resolver never substitutes the only symbol in a file. A call inside a symbol
uses that symbol as its source; a top-level call retains its observed
file/module source, and recursive calls may produce an intentional self-edge.
This applies identically to `calls`, `implements`, `routes_to`, and `injects`.
TypeScript extraction emits `implements` for direct concrete or abstract class
clauses, and generic targets use their AST base reference while retaining
evidence over the complete clause. `extends` is intentionally not repurposed
as an `implements` fact.

`injects` (#95) resolves a Python `Depends(name)` argument the same way a
`call` does: the extractor records only the bare referenced name and its
source span; the resolver attributes it to whichever symbol's stored span
contains it (the function whose default argument reads `Depends(name)`), then
looks up `name` through the identical same-file-definition /
`import_binding`-only rule above. A dependency imported from another module,
or one this fixture never defines (e.g. a bare `oauth2_scheme` reference with
no local definition), stays an honest `RI-RES-UNRESOLVED` diagnostic rather
than a guessed edge.

### Service interactions (#209)

An `http_call` referent is the extractor's three-part
`METHOD|origin|path` record — the same delimited representation `import_binding`
uses, and for the same reason: it is direct extractor output, not resolver
interpretation. The resolver splits it and looks up exactly one deterministic
key, `svc:<origin>`. There is no search and no nearest-match: the extractor that
proved the literal URL also emitted the `service` node for that origin, so
either the key is present or the observation stays `RI-RES-UNRESOLVED`. A
referent that does not carry all three parts is never repaired.

The call is attributed to whichever symbol's stored span contains it, falling
back to the observed file/module — identical to how a `calls` reference picks
its source, so both predicates agree about who made a call.

Only the origin is the service's identity. The method and path vary per call
site and live on the observation, so `GET https://api.example.com/v1/users` and
`POST https://api.example.com/v1/orders` are two calls to **one** service rather
than two services. That identity is language-neutral, so a Python and a
TypeScript call site to the same origin converge on one node.

### Lockfile resolutions (#209)

A `resolution` observation records that a lockfile pinned a dependency to an
exact version. It is deliberately **not** a relationship input. A lockfile entry
proves that a version was installed; it does not prove the repository depends on
that package directly, and most entries in a real lockfile are transitive. Only
a manifest-backed `dependency` observation produces `depends_on`, so no
transitive resolution is ever implied by a `depends_on` edge.

The resolution is retained as an observation on the dependency node rather than
downgraded to a diagnostic: nothing about it is unresolved, it simply is not a
relationship claim. The merged dependency node keeps `declarations` and
`resolutions` as separate collections, and an empty `resolutions` list is the
honest statement that no supported lockfile pinned that dependency.

### Infrastructure resources (#209)

An `iac_resource` observation whose subject is an `iac_resource` node in the
snapshot resolves `repo:root -[declares]-> <resource>`, exactly like a manifest
`dependency` observation resolves `depends_on`. An observation whose subject is
absent or is some other node kind stays unresolved rather than attaching an
arbitrary node to the repository.

### Routes

Extractors create an observed anonymous route symbol for each literal route
declaration. A `route_handler` observation must name exactly one direct handler
reference for the route. Python decorators bind the route to their decorated
function. TypeScript records static `Component`, `component`, and JSX `element`
references. Lazy, computed, or otherwise unsupported route handlers remain
unresolved rather than being inferred from a path. A dynamic JSX/object route
path produces `RI-EXT-UNSUPPORTED`; it is never materialized as a literal route
property or used as the subject of a resolved route relationship.

## Truth classes and provenance

The resolver emits only `resolved` edges through `SnapshotStore.add_edge`. Each
edge has `relationship-resolver@1.1.0` as its immediate producer, carries the
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
dependency is present. Adversarial cases cover local parameter shadowing in
both languages, module-local Python import bindings, default-imported React
route handlers, dynamic JSX route paths, top-level and recursive calls, and
abstract generic `implements` clauses. All warning paths are sealed
successfully to prove that honest partial knowledge remains usable.

`tests/intelligence/test_service_and_iac_resolution.py` covers the #209 kinds:
a proven call resolving to its origin's service node and being attributed to the
containing symbol, a top-level call falling back to its module, an origin with no
service node and a malformed referent both staying unresolved, an `iac_resource`
observation attaching to `repo:root`, and — the negative that matters most — a
lockfile `resolution` producing neither an edge nor a diagnostic while a manifest
declaration for the same dependency still produces `depends_on`. Edge truth class,
producer identity, evidence span, and observation derivation are asserted
directly rather than inferred from a count.
