from __future__ import annotations

from pathlib import Path

import pytest

from app.analysis.resource_budget import AnalysisResourceBudget, AnalysisResourceExceeded
from app.analysis.source_stream import RepositorySourceStream, UnsafeSourcePath


def _budget(
    *,
    source_bytes: int = 1024,
    rss_bytes: int = 1024,
    seconds: float = 60,
    rss_reader=lambda: 1,
    monotonic=lambda: 0.0,
) -> AnalysisResourceBudget:
    return AnalysisResourceBudget(
        max_source_bytes=source_bytes,
        max_rss_bytes=rss_bytes,
        max_seconds=seconds,
        rss_reader=rss_reader,
        monotonic=monotonic,
    )


def test_source_budget_fails_before_accepting_an_oversized_repository():
    budget = _budget(source_bytes=5)

    budget.charge_source(3)

    with pytest.raises(AnalysisResourceExceeded, match="source_bytes budget exceeded") as caught:
        budget.charge_source(3)
    assert caught.value.resource == "source_bytes"
    assert budget.source_bytes == 3


def test_rss_and_elapsed_budgets_track_the_observed_high_watermark():
    rss_values = iter((10, 80))
    budget = _budget(
        rss_bytes=50,
        seconds=10,
        rss_reader=lambda: next(rss_values),
    )

    budget.check()
    with pytest.raises(AnalysisResourceExceeded, match="rss_bytes budget exceeded"):
        budget.check()
    assert budget.peak_rss_bytes == 80


def test_elapsed_budget_is_fail_closed():
    times = iter((0.0, 11.0))
    budget = _budget(seconds=10, monotonic=lambda: next(times))

    with pytest.raises(AnalysisResourceExceeded, match="elapsed_seconds budget exceeded"):
        budget.check()


@pytest.mark.parametrize("observed_rss", (10, 20, 30), ids=("small", "medium", "large"))
def test_sized_fixture_rss_samples_stay_within_the_enforced_budget(observed_rss: int):
    budget = _budget(rss_bytes=40, rss_reader=lambda: observed_rss)

    budget.check()

    assert budget.peak_rss_bytes == observed_rss


def test_independent_budgets_do_not_cross_contaminate():
    # Two separate analysis runs must never share charged state -- a shared
    # counter here would mean one repository's byte usage silently eats into
    # another's budget headroom.
    first = _budget(source_bytes=10)
    second = _budget(source_bytes=10)

    first.charge_source(9)

    assert first.source_bytes == 9
    assert second.source_bytes == 0
    # The second budget's own headroom is untouched by the first's charge.
    second.charge_source(9)
    assert second.source_bytes == 9


def test_repository_source_stream_is_sorted_bounded_and_charged(tmp_path: Path):
    (tmp_path / "z.py").write_bytes(b"z = 1\n")
    (tmp_path / "a.py").write_bytes(b"a = 1\n")
    tree = [
        {"type": "file", "path": "z.py"},
        {"type": "file", "path": "/a.py"},
        {"type": "file", "path": "a.py"},
    ]
    budget = _budget(source_bytes=100)

    sources = list(
        RepositorySourceStream(
            root=tmp_path,
            file_tree=tree,
            max_file_bytes=4,
            budget=budget,
        )
    )

    assert sources == [("a.py", b"a = 1"), ("z.py", b"z = 1")]
    assert budget.source_bytes == 12


def test_repository_source_stream_rejects_symlinks(tmp_path: Path):
    target = tmp_path / "target.py"
    target.write_bytes(b"x = 1\n")
    link = tmp_path / "link.py"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("creating symlinks is not permitted on this platform")

    stream = RepositorySourceStream(
        root=tmp_path,
        file_tree=[{"type": "file", "path": "link.py"}],
        max_file_bytes=512,
        budget=_budget(),
    )

    with pytest.raises(UnsafeSourcePath, match="traverses a symlink"):
        list(stream)


def test_repository_source_stream_rejects_manifest_path_escape(tmp_path: Path):
    stream = RepositorySourceStream(
        root=tmp_path,
        file_tree=[{"type": "file", "path": "../outside.py"}],
        max_file_bytes=512,
        budget=_budget(),
    )

    with pytest.raises(UnsafeSourcePath, match="escapes the repository root"):
        list(stream)


def test_repository_source_stream_rejects_non_regular_files(tmp_path: Path):
    # A directory is not a symlink, so it reaches the post-open fstat check
    # rather than the symlink-component check -- and unlike a FIFO or a
    # socket special file, opening a directory O_RDONLY is universally safe
    # and never blocks, so this exercises the stat.S_ISREG rejection directly
    # without any platform-specific setup or risk of hanging the test.
    (tmp_path / "not-a-file").mkdir()

    stream = RepositorySourceStream(
        root=tmp_path,
        file_tree=[{"type": "file", "path": "not-a-file"}],
        max_file_bytes=512,
        budget=_budget(),
    )

    with pytest.raises(UnsafeSourcePath, match="is not a regular file"):
        list(stream)


def test_repository_source_stream_skips_files_removed_after_ingestion(tmp_path: Path):
    (tmp_path / "kept.py").write_bytes(b"kept = 1\n")
    removed_path = tmp_path / "removed.py"
    removed_path.write_bytes(b"removed = 1\n")
    tree = [
        {"type": "file", "path": "kept.py"},
        {"type": "file", "path": "removed.py"},
    ]
    budget = _budget()
    stream = RepositorySourceStream(root=tmp_path, file_tree=tree, max_file_bytes=512, budget=budget)

    # The manifest still names removed.py -- the record was ingested, then the
    # stored file vanished before this analysis run read it. That must be
    # skipped silently, not raised, per the stream's existing policy.
    removed_path.unlink()

    sources = list(stream)

    assert sources == [("kept.py", b"kept = 1\n")]
