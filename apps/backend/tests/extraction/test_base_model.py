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
    ev = ExtractedEvidence(path="src/main.py", start_line=1, end_line=1, logical_line_count=1)
    node = ExtractedNode(
        node_kind="file",
        stable_key="file:src/main.py",
        name="main.py",
        language="python",
        evidence=(ev,),
    )
    obs = ExtractedObservation(
        observed_kind="import",
        subject_kind="file",
        subject_key="file:src/main.py",
        referent_text="os",
        ordinal=1,
        evidence=ev,
    )
    diag = ExtractedDiagnostic(
        code="RI-EXT-UNSUPPORTED",
        category="unsupported construct",
        severity="info",
        message="star import is unsupported",
    )
    result = ExtractionResult(nodes=(node,), observations=(obs,), diagnostics=(diag,))

    assert result.nodes[0].stable_key == "file:src/main.py"
    assert result.observations[0].referent_text == "os"
    assert result.diagnostics[0].severity == "info"
    assert ev.granularity == "span"  # default
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.name = "other"  # type: ignore[misc]
