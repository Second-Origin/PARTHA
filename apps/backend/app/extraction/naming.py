from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.intelligence import canonical


def symbol_stable_key(path: str, scope: Sequence[str], name: str) -> str:
    """Build ``<file-path>::<qualified.name>`` (RFC §4.3), path normalized."""

    normalized = canonical.normalize_repo_path(path)
    qualified = ".".join([*scope, name])
    return f"{normalized}::{qualified}"


class DiscriminatorAssigner:
    """Assigns RFC §4.3 ``#<n>`` discriminators by source order within one file.

    The first occurrence of a base symbol key is returned unchanged; each later
    occurrence gets ``#2``, ``#3``, … The second return value is ``True`` when a
    discriminator was appended, so the caller can emit an ``RI-KEY-DUP-SYMBOL``
    diagnostic. Instantiate one per file so counters are revision-local.
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)

    def key(self, base_symbol_key: str) -> tuple[str, bool]:
        self._counts[base_symbol_key] += 1
        n = self._counts[base_symbol_key]
        if n == 1:
            return base_symbol_key, False
        return f"{base_symbol_key}#{n}", True
