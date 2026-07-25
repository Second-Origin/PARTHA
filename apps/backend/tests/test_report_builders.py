from app.reports.builders import build_architecture_document, build_dependencies_document
from app.reports.renderers import render_html, render_markdown
from app.schemas.architecture import (
    ArchitectureResponse,
    ArchitectureSummary,
    ArchLayer,
    ArchModule,
    ArchNode,
    RequestFlowStep,
)
from app.schemas.dependencies import (
    DependencyAssessment,
    DependencyGraphResponse,
    DependencyNode,
    DependencyProvenance,
)


def _architecture() -> ArchitectureResponse:
    return ArchitectureResponse(
        repository_id="repo-1",
        repository_name="sample",
        architecture_type="Backend Service",
        detected_layers=[ArchLayer(id="business-logic", name="Business Logic", order=1, nodes=["module:services"])],
        nodes=[
            ArchNode(
                id="module:services",
                name="Services",
                type="service",
                description="Service module.",
                responsibilities=["Owns service concerns"],
                files=["app/services/analysis_service.py"],
                dependencies=[],
                dependents=[],
                estimated_complexity="medium",
                estimated_lines=160,
                tags=["business-logic", "service"],
                layer="business-logic",
            )
        ],
        edges=[],
        modules=[
            ArchModule(id="module:services", name="Services", layer="business-logic", node_ids=["module:services"], description="Services module.", file_count=2)
        ],
        request_flow=[RequestFlowStep(id="service", name="Service Layer", type="service", description="Business logic executes.", details=["Transform data"])],
        summary=ArchitectureSummary(
            language="Python",
            framework="FastAPI",
            total_modules=1,
            total_nodes=1,
            entry_point="app/main.py",
            architecture_pattern="Backend Service",
        ),
    )


def _dependency_provenance() -> DependencyProvenance:
    return DependencyProvenance(
        snapshot_id="snap_example",
        snapshot_schema_version="ri.v1",
        canonical_graph_hash="sha256:" + "1" * 64,
    )


def _dependencies() -> DependencyGraphResponse:
    return DependencyGraphResponse(
        repository_id="repo-1",
        repository_name="sample",
        revision_kind="upload",
        revision_value="sha256:" + "0" * 64,
        snapshot_id="snap_example",
        snapshot_schema_version="ri.v1",
        canonical_graph_hash="sha256:" + "1" * 64,
        manifest_digest="sha256:" + "2" * 64,
        provenance=_dependency_provenance(),
        generated_at="2026-07-17T00:00:00Z",
        nodes=[
            DependencyNode(
                id="dep:npm:react",
                name="react",
                version="^18.0.0",
                type="production",
                ecosystem="npm",
                declarations=[],
            ),
            DependencyNode(
                id="dep:npm:vite",
                name="vite",
                version="^5.0.0",
                type="development",
                ecosystem="npm",
                declarations=[],
            ),
        ],
        edges=[],
        total_dependencies=2,
        vulnerability_assessment=DependencyAssessment(status="not_computed"),
        outdated_assessment=DependencyAssessment(status="not_computed"),
    )


def test_build_architecture_document_has_evidence_and_renders():
    document = build_architecture_document(_architecture())

    headings = [section.heading for section in document.sections]
    assert "Overview" in headings
    assert "Layers" in headings
    assert "Modules" in headings

    markdown = render_markdown(document)
    assert "# Architecture Overview: sample" in markdown
    assert "app/services/analysis_service.py" in markdown  # evidence file surfaced
    assert render_html(document).startswith("<!DOCTYPE html>")


def test_build_dependencies_document_lists_inventory():
    document = build_dependencies_document(_dependencies(), "sample")

    markdown = render_markdown(document)
    assert "# Dependencies: sample" in markdown
    assert "| react | ^18.0.0 | production |" in markdown
    assert "| Vulnerability assessment | Not computed |" in markdown
    assert "| Outdated-version assessment | Not computed |" in markdown
    assert "outside the current analysis scope" in markdown  # no fabricated vuln counts


def test_build_dependencies_document_handles_empty_inventory():
    empty = DependencyGraphResponse(
        repository_id="repo-1",
        repository_name="sample",
        revision_kind="upload",
        revision_value="sha256:" + "0" * 64,
        snapshot_id="snap_example",
        snapshot_schema_version="ri.v1",
        canonical_graph_hash="sha256:" + "1" * 64,
        manifest_digest="sha256:" + "2" * 64,
        provenance=_dependency_provenance(),
        generated_at="2026-07-17T00:00:00Z",
        nodes=[],
        edges=[],
        total_dependencies=0,
        vulnerability_assessment=DependencyAssessment(status="not_computed"),
        outdated_assessment=DependencyAssessment(status="not_computed"),
    )

    document = build_dependencies_document(empty, "sample")
    markdown = render_markdown(document)

    assert "No dependencies were detected." in markdown
    assert "| Vulnerability assessment | Not computed |" in markdown
    assert "| Outdated-version assessment | Not computed |" in markdown
