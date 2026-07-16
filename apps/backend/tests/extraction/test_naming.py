from app.extraction.naming import DiscriminatorAssigner, symbol_stable_key


def test_symbol_stable_key_builds_qualified_dotted_name():
    assert symbol_stable_key("src/auth/service.ts", [], "issueToken") == \
        "src/auth/service.ts::issueToken"
    assert symbol_stable_key("src/auth/service.ts", ["AuthService"], "login") == \
        "src/auth/service.ts::AuthService.login"
    assert symbol_stable_key("app/api/auth.py", ["outer"], "_inner") == \
        "app/api/auth.py::outer._inner"


def test_discriminator_numbers_duplicates_in_source_order():
    assigner = DiscriminatorAssigner()
    base = "a.ts::fmt"
    assert assigner.key(base) == ("a.ts::fmt", False)
    assert assigner.key(base) == ("a.ts::fmt#2", True)
    assert assigner.key(base) == ("a.ts::fmt#3", True)
    # a different key is independent
    assert assigner.key("a.ts::other") == ("a.ts::other", False)
