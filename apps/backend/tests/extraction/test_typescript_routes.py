from app.extraction.typescript import TypeScriptExtractor

EXTRACTOR = TypeScriptExtractor()


def test_create_browser_router_paths_become_route_observations():
    source = (
        "import { createBrowserRouter } from 'react-router-dom';\n"
        "export const router = createBrowserRouter([\n"
        "  { path: '/login', element: null },\n"
        "  { path: '/dashboard', element: null },\n"
        "]);\n"
    )
    result = EXTRACTOR.extract("src/app/routes/router.ts", source.encode("utf-8"))
    paths = sorted(o.referent_text for o in result.observations if o.observed_kind == "route")
    assert paths == ["/dashboard", "/login"]


def test_jsx_route_path_becomes_route_observation():
    source = "const x = <Route path='/settings' />;\n"
    result = EXTRACTOR.extract("src/app/routes/tree.tsx", source.encode("utf-8"))
    paths = [o.referent_text for o in result.observations if o.observed_kind == "route"]
    assert paths == ["/settings"]
