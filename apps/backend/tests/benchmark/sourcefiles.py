"""Byte- and line-level helpers over fixture source, per RFC-0001 §6.2.

Line evidence in ``ri.v1`` is defined over a *strict UTF-8 decode* of the stored
file bytes, and ``logical_line_count = 1 + count(U+000A)``. These helpers are the
single implementation of that convention for the benchmark, so the loader,
provenance validator, and any future extractor adapter all agree byte-for-byte.
"""

from __future__ import annotations

from pathlib import Path


class SourceDecodeError(ValueError):
    """Raised when fixture bytes are not valid strict UTF-8 (RI-SRC-MALFORMED)."""


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def is_binary(data: bytes) -> bool:
    """A non-empty file containing a NUL byte is binary (RFC §6.2, RI-SRC-BINARY).

    A zero-byte file is text, not binary.
    """

    return b"\x00" in data


def decode_strict_utf8(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:  # pragma: no cover - message is exercised via loader
        raise SourceDecodeError(str(exc)) from exc


def logical_line_count(text: str) -> int:
    """``1 + count(U+000A)`` — an empty string is one logical (empty) line."""

    return 1 + text.count("\n")


def logical_line_count_of_bytes(data: bytes) -> int:
    return logical_line_count(decode_strict_utf8(data))
