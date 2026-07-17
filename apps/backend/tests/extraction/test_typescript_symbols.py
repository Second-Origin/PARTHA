from app.extraction.typescript import TypeScriptExtractor

EXTRACTOR = TypeScriptExtractor()


def _keys(source: str):
    result = EXTRACTOR.extract("src/auth/service.ts", source.encode("utf-8"))
    return {n.stable_key for n in result.nodes if n.node_kind == "symbol"}, result


def test_class_methods_and_function_qualified_names():
    # Two methods prove the traversal reaches every method_definition inside
    # class_body, not just the class declaration itself.
    keys, _ = _keys(
        "export class AuthService {\n"
        "  login() {}\n"
        "  logout() {}\n"
        "}\n"
        "export function issueToken() {}\n"
    )
    assert "src/auth/service.ts::AuthService" in keys
    assert "src/auth/service.ts::AuthService.login" in keys
    assert "src/auth/service.ts::AuthService.logout" in keys
    assert "src/auth/service.ts::issueToken" in keys


def test_interface_type_enum_are_symbols():
    keys, _ = _keys(
        "export interface Session {}\n"
        "export type Id = string;\n"
        "export enum Role { Admin }\n"
    )
    assert "src/auth/service.ts::Session" in keys
    assert "src/auth/service.ts::Id" in keys
    assert "src/auth/service.ts::Role" in keys


def test_duplicate_overloads_get_discriminator():
    keys, result = _keys(
        "export function fmt(x: number): string;\n"
        "export function fmt(x: string): string;\n"
        "export function fmt(x: any): string { return String(x); }\n"
    )
    assert "src/auth/service.ts::fmt" in keys
    assert "src/auth/service.ts::fmt#2" in keys
    assert any(d.code == "RI-KEY-DUP-SYMBOL" for d in result.diagnostics)


def test_top_level_const_becomes_symbol_with_exported_flag():
    keys, result = _keys(
        "export const router = createBrowserRouter([]);\n"
        "const helper = 1;\n"
    )
    assert "src/auth/service.ts::router" in keys
    assert "src/auth/service.ts::helper" in keys
    router = next(n for n in result.nodes if n.stable_key == "src/auth/service.ts::router")
    assert router.properties is not None and router.properties.get("exported") is True
    helper = next(n for n in result.nodes if n.stable_key == "src/auth/service.ts::helper")
    assert helper.properties is None or helper.properties.get("exported") is not True


def test_exported_function_carries_exported_property():
    _, result = _keys("export function issueToken() {}\n")
    token = next(
        n for n in result.nodes if n.stable_key == "src/auth/service.ts::issueToken"
    )
    assert token.properties is not None and token.properties.get("exported") is True


def test_direct_implements_clause_becomes_a_resolver_observation():
    _, result = _keys("interface Worker {}\nclass Runner implements Worker {}\n")
    observations = [
        (observation.subject_key, observation.referent_text)
        for observation in result.observations
        if observation.observed_kind == "implements"
    ]
    assert observations == [("src/auth/service.ts::Runner", "Worker")]
