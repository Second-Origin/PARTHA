from app.extraction.base import decode_source, logical_line_count


def test_logical_line_count_matches_rfc_convention():
    assert logical_line_count("") == 1  # empty file = 1 logical line
    assert logical_line_count("a") == 1
    assert logical_line_count("a\n") == 2  # trailing newline = final empty line
    assert logical_line_count("a\r\nb") == 2  # \r\n counts once (only \n)
    assert logical_line_count("a\nb\nc") == 3


def test_decode_source_accepts_utf8_text():
    text, diag = decode_source("src/main.py", b"print('hi')\n", producer="python-ast@1.0.0")
    assert text == "print('hi')\n"
    assert diag is None


def test_decode_source_flags_binary_with_nul_byte():
    text, diag = decode_source("logo.png", b"\x89PNG\x00\x00", producer="python-ast@1.0.0")
    assert text is None
    assert diag is not None
    assert diag.code == "RI-SRC-BINARY"
    assert diag.severity == "info"
    assert diag.path == "logo.png"


def test_decode_source_flags_malformed_utf8_as_error():
    text, diag = decode_source("bad.py", b"\xff\xfe\x00bad", producer="python-ast@1.0.0")
    # \x00 present -> binary takes precedence per RFC (NUL => binary)
    assert diag.code == "RI-SRC-BINARY"

    text2, diag2 = decode_source("bad2.py", b"\xff\xfeabc", producer="python-ast@1.0.0")
    assert text2 is None
    assert diag2.code == "RI-SRC-MALFORMED"
    assert diag2.severity == "error"


def test_empty_file_decodes_to_text_not_binary():
    text, diag = decode_source("empty.py", b"", producer="python-ast@1.0.0")
    assert text == ""
    assert diag is None
