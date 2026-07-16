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


def _routes(path: str, source: str):
    result = EXTRACTOR.extract(path, source.encode("utf-8"))
    return [o.referent_text for o in result.observations if o.observed_kind == "route"]


def test_plain_object_path_property_is_not_a_route():
    # An ordinary object that happens to have a `path` key is not a router entry.
    assert _routes("src/config.ts", "const cfg = { path: '/tmp/cache', size: 10 };\n") == []


def test_non_route_jsx_component_path_attribute_is_not_a_route():
    # `path` on a non-Route component is not a react-router route.
    assert _routes("src/f.tsx", "const x = <File path='/tmp/x' />;\n") == []


def test_nested_router_children_are_routes():
    source = (
        "export const router = createBrowserRouter([\n"
        "  { path: '/', children: [{ path: '/nested' }] },\n"
        "]);\n"
    )
    assert sorted(_routes("src/app/routes/router.ts", source)) == ["/", "/nested"]


def test_router_options_argument_is_not_a_route_table():
    # createBrowserRouter(routes, opts) — only the first argument is the route
    # table; `path` in the options object is not a route.
    source = "const router = createBrowserRouter(routes, { path: '/not-a-route' });\n"
    assert _routes("src/app/routes/router.ts", source) == []


def test_router_options_argument_ignored_while_route_table_still_read():
    source = (
        "const router = createBrowserRouter(\n"
        "  [{ path: '/login' }],\n"
        "  { path: '/not-a-route', future: {} },\n"
        ");\n"
    )
    assert _routes("src/app/routes/router.ts", source) == ["/login"]


def test_route_inside_createbrowserrouter_variable_is_not_matched_elsewhere():
    # A `path` key in an unrelated object in the same file stays unmatched.
    source = (
        "export const router = createBrowserRouter([{ path: '/login' }]);\n"
        "const opts = { path: '/not-a-route' };\n"
    )
    assert _routes("src/app/routes/router.ts", source) == ["/login"]
