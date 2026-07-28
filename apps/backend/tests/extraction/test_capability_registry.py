"""Focused tests for the authoritative capability registry and README view."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.extraction.support_matrix import (
    CAPABILITY_REGISTRY,
    PUBLIC_CAPABILITIES,
    README_CAPABILITIES_END,
    README_CAPABILITIES_START,
    PublicStatus,
    SupportStatus,
    check_readme_capabilities,
    render_readme_capabilities,
    validate_registry,
)


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


def test_readme_capability_rendering_is_byte_stable_and_checked_in():
    assert render_readme_capabilities() == render_readme_capabilities()
    readme = Path(__file__).parents[4] / "README.md"
    check_readme_capabilities(readme)
    block = readme.read_text(encoding="utf-8")
    assert block.count(README_CAPABILITIES_START) == 1
    assert block.count(README_CAPABILITIES_END) == 1


def test_stale_readme_capability_claims_fail_check(tmp_path: Path):
    readme = tmp_path / "README.md"
    content = (Path(__file__).parents[4] / "README.md").read_text(encoding="utf-8")
    readme.write_text(
        content.replace("Archive upload and public GitHub import", "Changed capability", 1), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="README capability registry block is stale"):
        check_readme_capabilities(readme)
