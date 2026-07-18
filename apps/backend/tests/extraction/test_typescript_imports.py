from app.extraction.typescript import TypeScriptExtractor

EXTRACTOR = TypeScriptExtractor()


def _extract(source: str):
    return EXTRACTOR.extract("src/auth/service.ts", source.encode("utf-8"))


def test_imports_become_observations():
    result = _extract(
        "import { issueToken } from './tokens';\n"
        "export { refresh } from './session';\n"
    )
    specifiers = sorted(
        o.referent_text for o in result.observations if o.observed_kind == "import"
    )
    assert specifiers == ["./session", "./tokens"]


def test_named_import_aliases_are_preserved_for_the_resolver():
    result = _extract("import { issueToken as mint } from './tokens';\nmint();\n")
    bindings = [
        observation.referent_text
        for observation in result.observations
        if observation.observed_kind == "import_binding"
    ]
    assert bindings == ["./tokens|issueToken|mint"]
