from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def test_runtime_lock_check(tmp_path, monkeypatch):
    spec = spec_from_file_location("runtime_lock", Path(__file__).parents[1] / "scripts/check_runtime_dependencies.py")
    checker = module_from_spec(spec)
    spec.loader.exec_module(checker)
    lock = tmp_path / "requirements.txt"
    lock.write_text("# reviewed\n\ndemo==1.2.3\n")
    monkeypatch.setattr(checker, "version", lambda name: "1.2.3")
    assert checker.check(lock) == []
    monkeypatch.setattr(checker, "version", lambda name: "1.0.0")
    assert checker.check(lock) == ["demo: installed 1.0.0, expected 1.2.3"]

    def missing(name):
        raise checker.PackageNotFoundError(name)

    monkeypatch.setattr(checker, "version", missing)
    assert checker.check(lock) == ["demo: missing (expected 1.2.3)"]
