# PARTHA Governance

This document describes how decisions get made and how change lands in PARTHA. It
summarizes rules that already live in other files and points at them; where a process is
not yet formalized, it says so rather than inventing one.

## Project scope

PARTHA is a Repository Intelligence platform: it turns a repository revision into a sealed,
queryable model and serves architecture, dependency, review, insight, documentation, and AI
context from it. The [capability matrix](docs/CAPABILITIES.md) is the current contract and
[ROADMAP.md](ROADMAP.md) is the direction. A guiding constraint runs through both: the
repository must not claim more than the implementation can defend, and documentation ships
in the same pull request as the behaviour it describes.

## Roles

| Role | Who | What it means |
| --- | --- | --- |
| **Project Lead** | [@parthrohit22](https://github.com/parthrohit22) | Final say on product direction, architecture, roadmap, and release coordination. May review across the whole repository, and is the project-wide fallback owner in [`.github/CODEOWNERS`](.github/CODEOWNERS). |
| **Area maintainers** | Listed in [MAINTAINERS.md](MAINTAINERS.md), with path ownership in [`.github/CODEOWNERS`](.github/CODEOWNERS) | Primary technical review for changes inside their ownership boundary (currently backend & infrastructure, and tests & documentation). Merge and release authority; maintain quality and architectural standards within their area. |
| **Contributors** | Anyone who opens an issue or pull request | Participate through the [contribution workflow](CONTRIBUTING.md). No standing permissions. |
| **RFC reviewers** | Named per RFC | Provide independent review of an architectural contract before it is accepted. Independent ratification is *requested* for significant RFCs and may be waived by the Project Lead, on the record, when a substantive independent check is not available (see RFC-0001 §1, RFC-0002 §1.2). |

Maintainer appointment, inactivity, and removal is **not yet a written process**. It is
currently the Project Lead's decision. As the maintainer group grows, that process should be
defined here.

## How change lands

All development targets `dev` through a pull request. The `Protect Dev` and `Protect Main`
repository rulesets (both active) require, for a merge:

- an approving review, including review from a code owner;
- all required status checks green (a reviewer approval does not override a failing check);
- no force-push and no branch deletion on the protected branch.

`main` only ever moves by promoting `dev` at a release point. See
[CONTRIBUTING §6–§8](CONTRIBUTING.md#6-pull-requests) for the full workflow and
[CONTRIBUTING §0](CONTRIBUTING.md#0-scope-discipline-merge-gate) for the scope-discipline
merge gate.

## Architectural decisions

Changes to an architectural contract — the `ri.v1` schema, the Repository Intelligence
boundary, revision or lineage identity, the evidence model — go through an **RFC** in
[`docs/architecture/`](docs/architecture/) before implementation. An RFC records the design,
its alternatives, and its status (`Accepted`, `Implemented`, superseded), and is approved by
a maintainer with, where available, independent review. Implementation is tracked as a
separate issue and the RFC's status is updated when it ships. RFC-0001 (`ri.v1`) and
RFC-0002 (Repository Lineage) are the existing examples.

## Releases

Releases are cut by maintainers: bump versions, promote `dev` → `main`, tag `vMAJOR.MINOR.PATCH`.
The tag triggers [`release.yml`](.github/workflows/release.yml), which re-validates against
PostgreSQL and Redis before publishing a GitHub Release; a maintainer then curates the
generated notes. Full steps are in [CONTRIBUTING §14](CONTRIBUTING.md#14-releases). PARTHA
is pre-1.0 and does not offer a long-term-support commitment — see [SUPPORT.md](SUPPORT.md).

## Security-sensitive decisions

Vulnerability reports are handled privately per [SECURITY.md](SECURITY.md) (private email,
72-hour acknowledgement target, coordinated fix and disclosure). A broader written process
for embargoes, CVE assignment, and downstream notification is **not yet defined** and should
be added as the project's exposure grows.

## Code of conduct

All participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).

## Changing this document

Governance changes are proposed as a pull request and require maintainer approval like any
other change. Where this document and a linked file disagree, the linked file is
authoritative and this document should be corrected.
