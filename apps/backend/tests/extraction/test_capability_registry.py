"""Focused tests for the authoritative capability registry and its generated docs view."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.extraction.support_matrix import (
    CAPABILITIES_BLOCK_END,
    CAPABILITIES_BLOCK_START,
    CAPABILITY_REGISTRY,
    PUBLIC_CAPABILITIES,
    PublicStatus,
    SupportStatus,
    check_capabilities_doc,
    render_capabilities_block,
    splice_capabilities_block,
    validate_registry,
)

CAPABILITIES_DOC = Path(__file__).parents[4] / "docs" / "CAPABILITIES.md"


def test_registry_is_typed_unique_and_deterministically_ordered():
    validate_registry()
    ids = [item.id for item in CAPABILITY_REGISTRY]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))
    assert all(isinstance(item.status, SupportStatus) for item in CAPABILITY_REGISTRY)


def test_registry_rejects_duplicate_ids_and_unknown_status():
    with pytest.raises(ValueError, match="duplicate capability ids"):
        validate_registry((CAPABILITY_REGISTRY[0], CAPABILITY_REGISTRY[0]))

    broken = CAPABILITY_REGISTRY[0]
    broken = broken.__class__(
        id=broken.id,
        language=broken.language,
        construct=broken.construct,
        status="unknown",  # type: ignore[arg-type]
        description=broken.description,
        limitation=broken.limitation,
        benchmark_ids=broken.benchmark_ids,
    )
    with pytest.raises(ValueError, match="unsupported status"):
        validate_registry((broken,))


def test_public_claims_resolve_to_consistent_registry_capabilities():
    validate_registry()
    assert all(isinstance(item.status, PublicStatus) for item in PUBLIC_CAPABILITIES)

    broken = replace(PUBLIC_CAPABILITIES[0], capability_ids=("product.missing",))
    with pytest.raises(ValueError, match="references unknown capability"):
        validate_registry(public_capabilities=(broken,))


def test_capabilities_doc_block_is_byte_stable_and_checked_in():
    assert render_capabilities_block() == render_capabilities_block()
    check_capabilities_doc(CAPABILITIES_DOC)
    content = CAPABILITIES_DOC.read_text(encoding="utf-8")
    assert content.count(CAPABILITIES_BLOCK_START) == 1
    assert content.count(CAPABILITIES_BLOCK_END) == 1


def test_stale_capabilities_doc_block_fails_check(tmp_path: Path):
    doc = tmp_path / "CAPABILITIES.md"
    content = CAPABILITIES_DOC.read_text(encoding="utf-8")
    doc.write_text(
        content.replace("Archive upload and public GitHub import", "Changed capability", 1), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="capability registry block is stale"):
        check_capabilities_doc(doc)


def test_splice_restores_a_mangled_block(tmp_path: Path):
    content = CAPABILITIES_DOC.read_text(encoding="utf-8")
    mangled = content.replace("Archive upload and public GitHub import", "Changed capability", 1)
    assert splice_capabilities_block(mangled) == content
