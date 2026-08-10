# Iteration 1 design QA

## Reference

- Figma prototype: Iteration 1, starting at node `285:2987`.
- Compared states: sign in, dashboard, architecture, AI Workspace, and Settings → AI Providers.
- Comparison viewport: 1224 × 768. Responsive checks: 320 × 768.
- Comparison images are local QA artifacts and are not part of the public repository.

## Result

- Brand: designer-supplied PARTHA logo is used in authentication and navigation; no substitute mark is generated.
- Visual system: the implementation matches the reference cream canvas, orange primary/action colour, outlined surfaces, compact sidebar, and low-shadow card treatment.
- Dashboard: hierarchy, metric cards, repository list, navigation, and control density match the reference while all values remain authentic fixture data.
- Architecture: the graph, tabs, manifest, toolbar, and evidence labels match the reference. At 1224px and 320px, the document and main region have equal client and scroll widths. React Flow has non-zero dimensions at both sizes and emits no dimension warning.
- AI Workspace: the question composer remains visible at both viewports. The reference's blank workspace state is corrected while keeping the disclosed Preview limitation and sealed-snapshot-only context.
- AI Providers: provider selection, model identifier, masked key field, saved/not-configured state, test action, and save action are visible and functional. No credentials were entered during QA.
- Upload: source tabs expose real tab/tabpanel state so the selected GitHub or archive input cannot disagree with the visible content.
- Authentication: the existing supported email/password flow is retained. The reference's Google and GitHub controls were not copied because those authentication methods do not exist in the current backend and would create fake interactions.
- Responsive and accessibility: keyboard focus styling is visible, mobile navigation remains a labelled modal drawer, page headers wrap, contained tables scroll internally, and no page-level horizontal scrolling was observed in the tested states.

## Evidence

- Browser measurements at 1224px: Dashboard, Architecture, AI Workspace, and AI Providers each reported `body.scrollWidth === body.clientWidth`; authenticated main regions also reported equal scroll and client widths.
- Browser measurements at 320px: Architecture reported a 320 × 288 graph and no document/main overflow; AI Workspace reported a visible composer ending above the viewport bottom.
- Automated checks: 41 frontend test files / 222 tests passed; frontend lint passed; production build passed. Backend verification covered 888 passing tests and 4 expected environment-gated skips; 886 passed in the full sandboxed run, and the two loopback TLS cases blocked by sandbox socket permissions passed when rerun with loopback permission.

final result: passed
