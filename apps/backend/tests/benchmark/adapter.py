"""Adapt real Repository Intelligence extraction output into benchmark facts.

The adapter contains no parsing logic. It runs the production extraction
pipeline over the fixture revision's stored bytes and maps the real immutable
``ExtractionResult`` contract into the benchmark's comparison model.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Protocol, runtime_checkable

from app.extraction.pipeline import ExtractionPipeline, ProducedExtraction
from app.extraction.python import PythonExtractor
from app.extraction.typescript import TypeScriptExtractor

from benchmark.facts import EvidenceSpan, Fact, canonical_value
from benchmark.loader import LoadedFixture


@runtime_checkable
class ExtractionAdapter(Protocol):
    """Produces the actual facts the product pipeline emits for a fixture."""

    name: str
    available: bool

    def extract(self, fixture: LoadedFixture) -> list[Fact]: ...


class RealExtractionAdapter:
    """Run the real Python/TypeScript extractors through production source policy."""

    name = "repository-intelligence-real-extractors"
    available = True
    scored_fact_types = frozenset({"node", "observation", "diagnostic"})

    def extract(self, fixture: LoadedFixture) -> list[Fact]:
        pipeline = ExtractionPipeline(
            (PythonExtractor(), TypeScriptExtractor()),
            max_source_bytes=fixture.max_source_bytes,
        )
        facts: list[Fact] = []
        for produced in pipeline.run(fixture.source_files()):
            facts.extend(self._convert(produced))
        return self._merge_compatible_nodes(facts)

    def _convert(self, produced: ProducedExtraction) -> list[Fact]:
        result = produced.result
        facts: list[Fact] = []
        for node in result.nodes:
            facts.append(
                Fact(
                    fact_type="node",
                    kind=node.node_kind,
                    subject=node.stable_key,
                    name=node.name or "",
                    language=node.language or "",
                    truth_class="observed",
                    value=(
                        canonical_value(dict(node.properties))
                        if node.properties is not None
                        else ""
                    ),
                    evidence=self._evidence(node.evidence, produced),
                    details={"properties": dict(node.properties or {})},
                )
            )
        for observation in result.observations:
            facts.append(
                Fact(
                    fact_type="observation",
                    kind=observation.observed_kind,
                    subject=observation.subject_key,
                    predicate=observation.observed_kind,
                    referent=observation.referent_text or "",
                    ordinal=observation.ordinal,
                    evidence=self._evidence((observation.evidence,), produced),
                    details={"subjectKind": observation.subject_kind},
                )
            )
        for diagnostic in result.diagnostics:
            location = canonical_value(
                {
                    "details": dict(diagnostic.details) if diagnostic.details is not None else None,
                    "path": diagnostic.path,
                    "span": (
                        {
                            "startLine": diagnostic.span[0],
                            "endLine": diagnostic.span[1],
                        }
                        if diagnostic.span is not None
                        else None
                    ),
                }
            )
            facts.append(
                Fact(
                    fact_type="diagnostic",
                    kind=diagnostic.code,
                    subject=diagnostic.subject or "",
                    severity=diagnostic.severity,
                    category=diagnostic.category,
                    message=diagnostic.message,
                    producer=produced.producer,
                    value=location,
                    details={
                        "path": diagnostic.path,
                        "span": diagnostic.span,
                        "diagnosticDetails": dict(diagnostic.details or {}),
                    },
                )
            )
        return facts

    @staticmethod
    def _evidence(records, produced: ProducedExtraction) -> tuple[EvidenceSpan, ...]:
        return tuple(
            EvidenceSpan(
                path=record.path,
                start_line=record.start_line,
                end_line=record.end_line,
                granularity=record.granularity,
                extractor=produced.producer_name,
                extractor_version=produced.producer_version,
            )
            for record in records
        )

    @staticmethod
    def _merge_compatible_nodes(facts: list[Fact]) -> list[Fact]:
        """Mirror evidence union while retaining exact duplicate emissions as FPs."""

        merged: OrderedDict[tuple[object, ...], Fact] = OrderedDict()
        seen_emissions: set[tuple[object, ...]] = set()
        duplicate_nodes: list[Fact] = []
        others: list[Fact] = []
        for fact in facts:
            if fact.fact_type != "node":
                others.append(fact)
                continue
            identity = (
                fact.kind,
                fact.subject,
                fact.name,
                fact.language,
                fact.truth_class,
                fact.value,
            )
            emission = (*identity, tuple(span.key() for span in fact.evidence))
            if emission in seen_emissions:
                duplicate_nodes.append(fact)
                continue
            seen_emissions.add(emission)
            existing = merged.get(identity)
            if existing is None:
                merged[identity] = fact
                continue
            evidence = tuple(
                sorted(
                    {*existing.evidence, *fact.evidence},
                    key=lambda span: span.key(),
                )
            )
            merged[identity] = Fact(
                fact_type="node",
                kind=fact.kind,
                subject=fact.subject,
                name=fact.name,
                language=fact.language,
                truth_class=fact.truth_class,
                value=fact.value,
                evidence=evidence,
                details=fact.details,
            )
        return [*merged.values(), *duplicate_nodes, *others]


def default_adapter() -> ExtractionAdapter:
    return RealExtractionAdapter()
