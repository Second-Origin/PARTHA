"""The extraction adapter boundary — where the real extractors plug in.

Precision/recall scoring needs *actual* facts from a real Repository
Intelligence extractor. Those extractors (and their published support matrices)
land in #89/#90, which are not merged into ``dev`` yet. This module defines the
seam so that:

- today, the runner uses :class:`UnavailableExtractionAdapter`, and the scoring
  stage is reported as ``deferred`` — never a fabricated perfect score; and
- when #89/#90 merge, a thin real adapter maps the extractor's ``ExtractionResult``
  onto :class:`~benchmark.facts.Fact` and the exact same scorer, provenance
  validator, and thresholds enforce quality with no other change.

The benchmark deliberately does **not** ship a second repository parser
(CONTRIBUTING §11.2, Issue #94): an adapter adapts the real extractor's output;
it does not re-implement extraction.

The future real adapter must populate ``Fact.name`` and ``Fact.language`` for
node output exactly as emitted by the extractor. These values are part of the
node comparison identity; non-node facts leave both fields empty.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from benchmark.facts import Fact
from benchmark.loader import LoadedFixture


@runtime_checkable
class ExtractionAdapter(Protocol):
    """Produces the actual facts an extractor emits for a fixture revision."""

    name: str
    available: bool

    def extract(self, fixture: LoadedFixture) -> list[Fact]:
        ...


class UnavailableExtractionAdapter:
    """The default adapter while #89/#90 are unmerged: no extractor is wired.

    ``available`` is ``False``, so the runner marks precision/recall ``deferred``
    rather than scoring golden facts against themselves (which would manufacture
    a meaningless perfect score the product's own rules forbid).
    """

    name = "unavailable (extractors land in #89/#90)"
    available = False

    def extract(self, fixture: LoadedFixture) -> list[Fact]:  # pragma: no cover - never called
        raise RuntimeError(
            "No Repository Intelligence extractor is available yet; precision/recall "
            "scoring is deferred until #89/#90 merge their extractors and support matrices."
        )


def default_adapter() -> ExtractionAdapter:
    return UnavailableExtractionAdapter()
