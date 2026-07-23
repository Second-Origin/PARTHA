from app.extraction.base import build_evidence


def test_valid_span_builds_normalized_evidence():
    ev, diag = build_evidence(
        "src/./auth/service.ts", 41, 58, 100, producer="typescript-ast@1.1.0"
    )
    assert diag is None
    assert ev.path == "src/auth/service.ts"  # normalized
    assert (ev.start_line, ev.end_line, ev.logical_line_count) == (41, 58, 100)


def test_reversed_or_out_of_range_span_is_rejected():
    ev, diag = build_evidence("a.py", 10, 5, 100, producer="python-ast@1.0.0")
    assert ev is None and diag.code == "RI-SPAN-INVALID" and diag.severity == "error"

    ev2, diag2 = build_evidence("a.py", 1, 200, 100, producer="python-ast@1.0.0")
    assert ev2 is None and diag2.code == "RI-SPAN-INVALID"


def test_escaping_path_is_rejected():
    ev, diag = build_evidence("../secrets/.env", 1, 1, 1, producer="python-ast@1.0.0")
    assert ev is None and diag.code == "RI-SEC-PATH-ESCAPE"


def test_file_granularity_is_carried_through():
    ev, diag = build_evidence(
        "empty.py", 1, 1, 1, producer="python-ast@1.0.0", granularity="file"
    )
    assert diag is None and ev.granularity == "file"
