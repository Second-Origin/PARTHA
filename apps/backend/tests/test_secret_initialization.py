from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from cryptography.fernet import Fernet
import pytest


@pytest.fixture()
def initializer():
    spec = spec_from_file_location("initialize_secrets", Path(__file__).parents[1] / "scripts/initialize_secrets.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.initialize


@pytest.mark.parametrize("auth,ai", [(False, False), (True, False), (False, True), (True, True)])
def test_partial_secrets_preserve_survivors(initializer, tmp_path, auth, ai):
    expected = {}
    if auth:
        expected["auth_secret_key"] = "a" * 64
    if ai:
        expected["ai_encryption_key"] = Fernet.generate_key().decode()
    for name, value in expected.items():
        (tmp_path / name).write_text(value)
    initializer(tmp_path)
    for name, value in expected.items():
        assert (tmp_path / name).read_text() == value
    assert len((tmp_path / "auth_secret_key").read_text()) >= 32
    Fernet((tmp_path / "ai_encryption_key").read_text().encode())
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    initializer(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("name", ["auth_secret_key", "ai_encryption_key"])
def test_corrupt_survivor_rejected_without_creating_other_key(initializer, tmp_path, name):
    (tmp_path / name).write_text("corrupt")
    with pytest.raises(ValueError, match="Invalid existing"):
        initializer(tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == [name]


def test_concurrent_initializers_never_rotate_keys(initializer, tmp_path):
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: initializer(tmp_path), range(4)))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ai_encryption_key", "auth_secret_key"]
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    initializer(tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("auth,ai", [("valid", "invalid"), ("invalid", "valid"), ("invalid", "invalid")])
def test_invalid_pair_preserves_all_existing_bytes(initializer, tmp_path, auth, ai):
    values = {
        "auth_secret_key": "a" * 64 if auth == "valid" else "bad",
        "ai_encryption_key": Fernet.generate_key().decode() if ai == "valid" else "bad",
    }
    for name, value in values.items():
        (tmp_path / name).write_text(value)
    with pytest.raises(ValueError, match="Invalid existing"):
        initializer(tmp_path)
    assert values == {p.name: p.read_text() for p in tmp_path.iterdir()}
