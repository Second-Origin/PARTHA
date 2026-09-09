"""Resolved dependency-version extraction from supported lockfiles (#209).

A manifest says what a project *asked for* (``"react": "^18.3.0"``); a lockfile
says what was actually *installed* (``18.3.1``). Those are different facts about
the same logical dependency, and conflating them would let a caret range be
presented as an installed version.

This extractor therefore emits a **resolution**, never a declaration. Both land
on the same ``dep:<ecosystem>:<name>`` identity built by
:func:`app.extraction.naming.dependency_stable_key`, and
:mod:`app.extraction.dependencies` merges them into one node carrying separate
``declarations`` and ``resolutions`` collections.

Supported formats — this list is exact, and anything outside it produces a
diagnostic rather than a guess:

``package-lock.json`` with ``lockfileVersion`` 2 or 3
    The ``packages`` object is read. An entry is a resolved registry package
    only when its key contains a ``node_modules/`` segment and it carries a
    string ``version``. The logical name is the segment after the *last*
    ``node_modules/``, so a nested ``node_modules/a/node_modules/b`` entry is a
    second resolution of ``b`` — npm's real "two installed versions" shape —
    rather than a separate package. Workspace link entries (``"link": true``)
    describe a symlink into the repository, not a resolved registry version, and
    are skipped. ``lockfileVersion`` 1 predates the ``packages`` table and is
    explicitly unsupported.

``poetry.lock`` with ``[metadata] lock-version`` major 1 or 2
    Each ``[[package]]`` table's ``name`` and ``version`` are read. ``tomllib``
    preserves array-of-tables order, so the i-th parsed table pairs positionally
    with the i-th ``[[package]]`` header located in the source.

Deliberately **not** supported, and reported as such: npm ``lockfileVersion`` 1,
``yarn.lock``, ``pnpm-lock.yaml``, ``Pipfile.lock``, ``uv.lock``, and
``pdm.lock``. No lockfile format is parsed by guessing at another's shape, and
no transitive dependency *graph* is reconstructed: an entry proves a version was
installed, not that the repository depends on it directly.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import posixpath
import re
import tomllib

from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
    RI_EXT_UNSUPPORTED,
    RI_SEC_PATH_ESCAPE,
    RI_SRC_MALFORMED,
    assign_ordinals,
    build_evidence,
    decode_source,
    logical_line_count,
)
from app.extraction.naming import dependency_stable_key
from app.extraction.structured import (
    StructureError,
    json_object_member_lines,
    toml_array_of_tables_lines,
)
from app.extraction.support_matrix import supported_lockfile_filenames
from app.intelligence import canonical

SUPPORTED_LOCKFILE_FILENAMES = supported_lockfile_filenames()

#: ``package-lock.json`` revisions whose ``packages`` table this extractor reads.
SUPPORTED_NPM_LOCKFILE_VERSIONS = (2, 3)
#: ``poetry.lock`` ``[metadata] lock-version`` majors whose ``[[package]]`` shape is read.
SUPPORTED_POETRY_LOCK_MAJORS = ("1", "2")

_NPM_SEGMENT = "node_modules/"
_LOCK_VERSION_MAJOR = re.compile(r"^(\d+)(?:\.|$)")


class _UnsupportedLockfile(Exception):
    """A lockfile is a supported *filename* in an unsupported *revision*.

    This is deliberately distinct from :class:`StructureError`: the file is not
    malformed, it is a format this extractor has not implemented. It becomes an
    ``RI-EXT-UNSUPPORTED`` disclosure so the blind spot is visible instead of
    silently producing zero resolutions.
    """


@dataclass(frozen=True)
class _Resolution:
    """One lockfile entry proving an installed version, with its source line."""

    ecosystem: str
    name: str
    version: str
    #: The lockfile's own key for this entry (npm's ``node_modules/...`` path,
    #: or the poetry package name). Two resolutions of one logical dependency
    #: differ here, so it is what keeps their merged records distinguishable.
    entry: str
    #: ``production`` / ``development`` / ``optional``, or ``None`` when the
    #: format does not record the distinction (see the format notes above).
    scope: str | None
    line: int


class LockfileExtractor:
    """Extract resolved dependency versions from supported lockfiles."""

    name = "dependency-lockfile"
    version = "1.0.0"

    @property
    def producer(self) -> str:
        return f"{self.name}@{self.version}"

    def supports(self, path: str) -> bool:
        return posixpath.basename(path) in SUPPORTED_LOCKFILE_FILENAMES

    def extract(self, path: str, source: bytes) -> ExtractionResult:
        text, source_diagnostic = decode_source(path, source, producer=self.producer)
        if text is None:
            assert source_diagnostic is not None  # decode_source pairs None text with a diagnostic
            return ExtractionResult(diagnostics=(source_diagnostic,))
        try:
            normalized_path = canonical.normalize_repo_path(path)
        except canonical.PathEscapeError:
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SEC_PATH_ESCAPE,
                        category="path escape",
                        severity="error",
                        message="source path is absolute or escapes the repository root",
                    ),
                )
            )

        line_count = logical_line_count(text)
        basename = posixpath.basename(normalized_path)
        file_subject = canonical.normalize_stable_key("file", f"file:{normalized_path}")
        try:
            if basename == "package-lock.json":
                resolutions = self._npm_resolutions(text)
                lockfile_format = "npm-package-lock"
            else:
                resolutions = self._poetry_resolutions(text)
                lockfile_format = "poetry-lock"
        except _UnsupportedLockfile as exc:
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_EXT_UNSUPPORTED,
                        category="unsupported construct",
                        severity="info",
                        # The message names this module's own closed vocabulary of
                        # format revisions; it never quotes repository content
                        # (RFC §13). The path says where to look.
                        message=str(exc),
                        path=normalized_path,
                        subject=file_subject,
                    ),
                )
            )
        except (json.JSONDecodeError, tomllib.TOMLDecodeError, StructureError, UnicodeDecodeError):
            return ExtractionResult(
                diagnostics=(
                    ExtractedDiagnostic(
                        code=RI_SRC_MALFORMED,
                        category="malformed source",
                        severity="error",
                        message="lockfile could not be parsed or has an unsupported structure",
                        path=normalized_path,
                        subject=file_subject,
                    ),
                )
            )

        workspace_path = posixpath.dirname(normalized_path) or "."
        nodes: list[ExtractedNode] = []
        observations: list[ExtractedObservation] = []
        diagnostics: list[ExtractedDiagnostic] = []
        for resolution in resolutions:
            stable_key = dependency_stable_key(resolution.ecosystem, resolution.name)
            evidence, diagnostic = build_evidence(
                normalized_path,
                resolution.line,
                resolution.line,
                line_count,
                producer=self.producer,
            )
            if evidence is None:
                if diagnostic is not None:
                    diagnostics.append(diagnostic)
                continue
            nodes.append(
                ExtractedNode(
                    node_kind="dependency",
                    stable_key=stable_key,
                    name=resolution.name,
                    language=None,
                    evidence=(evidence,),
                    properties={
                        "ecosystem": resolution.ecosystem,
                        "resolved_version": resolution.version,
                        "dependency_scope": resolution.scope,
                        "lockfile_path": normalized_path,
                        "lockfile_format": lockfile_format,
                        "lockfile_entry": resolution.entry,
                        "workspace_path": workspace_path,
                    },
                )
            )
            observations.append(
                ExtractedObservation(
                    observed_kind="resolution",
                    subject_kind="dependency",
                    subject_key=stable_key,
                    # The pinned version is the fact this observation carries;
                    # the name is already the subject's identity.
                    referent_text=resolution.version,
                    ordinal=0,
                    evidence=evidence,
                )
            )
        return ExtractionResult(
            nodes=tuple(nodes),
            observations=assign_ordinals(observations),
            diagnostics=tuple(diagnostics),
        )

    # --- npm ----------------------------------------------------------------

    @staticmethod
    def _npm_resolutions(text: str) -> list[_Resolution]:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise StructureError("package-lock.json root is not an object")
        lockfile_version = parsed.get("lockfileVersion")
        if not isinstance(lockfile_version, int) or isinstance(lockfile_version, bool):
            raise StructureError("package-lock.json has no integer lockfileVersion")
        if lockfile_version not in SUPPORTED_NPM_LOCKFILE_VERSIONS:
            raise _UnsupportedLockfile(
                "package-lock.json lockfileVersion is outside the supported set "
                f"{list(SUPPORTED_NPM_LOCKFILE_VERSIONS)} and no resolutions are claimed"
            )
        packages = parsed.get("packages")
        if not isinstance(packages, dict):
            raise StructureError("package-lock.json has no packages object")
        entry_lines = json_object_member_lines(text).get("packages", {})

        resolutions: list[_Resolution] = []
        # Sorted so the emitted order depends on the lockfile's content, not on
        # dict insertion order; the line lookup below keeps provenance exact.
        for entry in sorted(packages):
            record = packages[entry]
            if not isinstance(record, dict):
                raise StructureError("package-lock.json packages entry is not an object")
            index = entry.rfind(_NPM_SEGMENT)
            if index < 0:
                # The root project ("") and workspace directory entries are not
                # resolved registry packages.
                continue
            if record.get("link") is True:
                continue
            name = entry[index + len(_NPM_SEGMENT) :]
            version = record.get("version")
            if not name or not isinstance(version, str) or not version:
                # An entry without a concrete installed version proves nothing;
                # ``add_node`` would otherwise receive a null pin.
                continue
            line = entry_lines.get(entry)
            if line is None:
                raise StructureError("package-lock.json entry line could not be located")
            resolutions.append(
                _Resolution(
                    ecosystem="npm",
                    name=name,
                    version=version,
                    entry=entry,
                    scope=LockfileExtractor._npm_scope(record),
                    line=line,
                )
            )
        return resolutions

    @staticmethod
    def _npm_scope(record: dict) -> str:
        """Map npm's tree flags onto the manifest ``dependency_type`` vocabulary.

        ``optional`` wins over ``dev`` because an optional install can be skipped
        entirely, which is the stronger caveat. npm's ``devOptional`` (reachable
        from both a dev and an optional edge) is reported as ``development``.
        """

        if record.get("optional") is True:
            return "optional"
        if record.get("dev") is True or record.get("devOptional") is True:
            return "development"
        return "production"

    # --- poetry -------------------------------------------------------------

    @staticmethod
    def _poetry_resolutions(text: str) -> list[_Resolution]:
        parsed = tomllib.loads(text)
        metadata = parsed.get("metadata")
        if not isinstance(metadata, dict):
            raise StructureError("poetry.lock has no [metadata] table")
        lock_version = metadata.get("lock-version")
        if not isinstance(lock_version, str):
            raise StructureError("poetry.lock has no lock-version string")
        major = _LOCK_VERSION_MAJOR.match(lock_version)
        if major is None or major.group(1) not in SUPPORTED_POETRY_LOCK_MAJORS:
            raise _UnsupportedLockfile(
                "poetry.lock lock-version major is outside the supported set "
                f"{list(SUPPORTED_POETRY_LOCK_MAJORS)} and no resolutions are claimed"
            )
        packages = parsed.get("package", [])
        if not isinstance(packages, list):
            raise StructureError("poetry.lock package is not an array of tables")
        if not packages:
            return []
        header_lines = toml_array_of_tables_lines(text, "package")
        # The scanner walks the same array the decoder did, in source order, so a
        # count mismatch means one of them saw structure the other did not — fail
        # closed rather than pair a version with the wrong line.
        if len(header_lines) != len(packages):
            raise StructureError("poetry.lock package headers could not be located")

        resolutions: list[_Resolution] = []
        for record, line in zip(packages, header_lines):
            if not isinstance(record, dict):
                raise StructureError("poetry.lock package entry is not a table")
            name = record.get("name")
            version = record.get("version")
            if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
                raise StructureError("poetry.lock package entry has no name/version pair")
            resolutions.append(
                _Resolution(
                    ecosystem="pypi",
                    name=name,
                    version=version,
                    entry=name,
                    scope=LockfileExtractor._poetry_scope(record),
                    line=line,
                )
            )
        return resolutions

    @staticmethod
    def _poetry_scope(record: dict) -> str | None:
        """Report poetry's group only when the lockfile actually records it.

        Poetry dropped the per-package ``category`` field in lock-version 2.0, so
        a modern ``poetry.lock`` genuinely does not say whether a package is a
        main or dev dependency. ``None`` states that honestly; guessing
        ``production`` would invent the distinction.
        """

        if record.get("optional") is True:
            return "optional"
        category = record.get("category")
        if category == "dev":
            return "development"
        if category == "main":
            return "production"
        return None
