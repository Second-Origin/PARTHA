"""Versioned schema constants for the benchmark fixture corpus.

Everything version- or vocabulary-bound lives here so a schema bump is a single,
reviewable change and the loader never carries magic strings inline.
"""

from __future__ import annotations

# Fixture manifest schema. Bumping this is a deliberate, reviewed migration.
FIXTURE_SCHEMA_VERSION = "ri-benchmark.v1"
SUPPORT_MATRIX_SCHEMA_VERSION = "ri-benchmark-support-matrix.v1"
THRESHOLDS_SCHEMA_VERSION = "ri-benchmark-thresholds.v1"

FIXTURE_CLASSES = ("minimal", "realistic", "adversarial")
LANGUAGES = ("python", "typescript", "mixed")

# Only synthetic upload bundles are supported today; a Git revision identity
# would require a real committed revision (RFC-0001 §3.2). The corpus is
# content-addressed by the SHA-256 of its stored bytes.
REVISION_IDENTITY_METHODS = ("upload-sha256",)

# ``ri.v1`` output kinds the manifest may declare under ``expected``.
FACT_GROUPS = ("nodes", "edges", "observations", "assertions", "diagnostics")

# Optional UTF-8 source entries injected into a fixture's stored revision. This
# permits adversarial raw paths that a host filesystem cannot materialize (for
# example a Windows-invalid backslash path) without weakening source-policy
# coverage or making the repository un-checkout-able on that host.
SYNTHETIC_FILES_FIELD = "syntheticFiles"

# RFC-0001 §8.2 diagnostic codes (the ``ri.v1`` baseline set).
DIAGNOSTIC_CODES = frozenset(
    {
        "RI-EXT-UNSUPPORTED",
        "RI-RES-AMBIGUOUS",
        "RI-RES-UNRESOLVED",
        "RI-EXT-FAILURE",
        "RI-SPAN-INVALID",
        "RI-KEY-COLLISION",
        "RI-KEY-DUP-SYMBOL",
        "RI-SRC-BINARY",
        "RI-SRC-MALFORMED",
        "RI-LIMIT-SKIP",
        "RI-SEC-PATH-ESCAPE",
        "RI-INT-FAILURE",
    }
)
DIAGNOSTIC_SEVERITIES = frozenset({"fatal", "error", "warning", "info"})

# A regeneration helper may validate/format hand-reviewed data, but golden truth
# must never be machine-blessed. A manifest carrying either of these truthy keys
# is rejected by the loader so an "update snapshots" workflow cannot slip in.
FORBIDDEN_BLESS_KEYS = ("blessed", "generated", "autoBlessed")
