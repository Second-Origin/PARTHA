from app.extraction.base import (
    ExtractedDiagnostic,
    ExtractedEvidence,
    ExtractedNode,
    ExtractedObservation,
    ExtractionResult,
    Extractor,
)
from app.extraction.pipeline import (
    DEFAULT_MAX_SOURCE_BYTES,
    ExtractionPipeline,
    ProducedExtraction,
)
from app.extraction.dependencies import (
    DEPENDENCY_SET_ARRAY_KEYS,
    merge_dependency_facts,
)
from app.extraction.iac import IacExtractor
from app.extraction.lockfiles import LockfileExtractor
from app.extraction.manifests import DependencyManifestExtractor
from app.extraction.python import PythonExtractor
from app.extraction.typescript import TypeScriptExtractor


def production_extractors() -> tuple[Extractor, ...]:
    """The extractor set durable analysis runs, in one place.

    Registering a new extractor here is what makes it real: the worker builds
    its pipeline from this tuple, ``AnalysisJobService`` derives the planned
    producer-version set from it (so submit and execution key on the identical
    semantic identity), and the golden benchmark measures it. A second hand-kept
    list anywhere else is how a producer ends up emitting facts a snapshot never
    declared, which fails sealing.
    """

    return (
        PythonExtractor(),
        TypeScriptExtractor(),
        DependencyManifestExtractor(),
        LockfileExtractor(),
        IacExtractor(),
    )


__all__ = [
    "ExtractedDiagnostic",
    "ExtractedEvidence",
    "ExtractedNode",
    "ExtractedObservation",
    "ExtractionResult",
    "Extractor",
    "DEFAULT_MAX_SOURCE_BYTES",
    "DEPENDENCY_SET_ARRAY_KEYS",
    "DependencyManifestExtractor",
    "ExtractionPipeline",
    "IacExtractor",
    "LockfileExtractor",
    "ProducedExtraction",
    "PythonExtractor",
    "TypeScriptExtractor",
    "merge_dependency_facts",
    "production_extractors",
]
