// Every leaf route is code-split via `lazy`, so the very first render always
// has at least one route whose module hasn't downloaded yet. Without a
// `HydrateFallback` on an ancestor, react-router renders nothing for that gap
// and logs "No `HydrateFallback` element provided to render during initial
// hydration" -- this component is that ancestor fallback, in the same visual
// style RequireAuth already uses for its own "session initialising" gap.
export function RootHydrateFallback() {
  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div
        role="status"
        aria-label="Loading"
        className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent"
      />
    </div>
  );
}
