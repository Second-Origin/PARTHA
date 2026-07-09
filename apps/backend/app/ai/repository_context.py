from app.ai.types import (
    ArchitectureContext,
    Citation,
    DependencyContext,
    DocumentationContext,
    EngineeringReviewContext,
    ModuleContext,
    RepositoryContext,
    RepositoryIdentity,
    SelectedFileContext,
)
from app.intelligence.engine import RepositoryIntelligenceEngine
from app.models.repository import RepositoryRecord


class RepositoryContextBuilder:
    def __init__(self, intelligence: RepositoryIntelligenceEngine) -> None:
        self.intelligence = intelligence

    def build(self, record: RepositoryRecord, selected_file: str | None = None) -> RepositoryContext:
        repository_intelligence = self.intelligence.from_record(record)
        files = [file.path for file in repository_intelligence.files]
        selected = [path for path in files if selected_file and path == selected_file]
        highlighted = selected or files[:40]
        modules = tuple(
            ModuleContext(
                name=module.name,
                role=module.role,
                file_count=len(module.files),
            )
            for module in repository_intelligence.modules[:10]
        )
        dependencies = tuple(
            DependencyContext(name=dependency.name, version=dependency.version)
            for dependency in repository_intelligence.dependencies[:20]
        )
        citations = tuple(
            Citation(
                file=path,
                start_line=1,
                end_line=1,
                content="Repository file path included in analysis context.",
            )
            for path in highlighted[:5]
        )
        return RepositoryContext(
            repository=RepositoryIdentity(id=record.id, name=record.name),
            architecture=ArchitectureContext(
                primary_language=repository_intelligence.discovery.primary_language,
                frameworks=tuple(repository_intelligence.discovery.frameworks),
                entry_points=tuple(repository_intelligence.discovery.entry_points),
                modules=modules,
            ),
            dependencies=dependencies,
            documentation=DocumentationContext(files=tuple(highlighted)),
            engineering_review=EngineeringReviewContext(),
            selected_files=tuple(SelectedFileContext(path=path) for path in highlighted),
            citations=citations,
        )
