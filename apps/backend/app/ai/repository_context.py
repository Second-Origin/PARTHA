from app.ai.types import (
    ArchitectureContext,
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
            DependencyContext(
                name=dependency.name,
                version=dependency.version,
                declared_versions=tuple(
                    dict.fromkeys(declaration.version for declaration in dependency.declarations)
                ),
                has_version_conflict=dependency.version is None
                and len({declaration.version for declaration in dependency.declarations}) > 1,
            )
            for dependency in repository_intelligence.dependencies[:20]
        )
        # No citations are emitted today: the context is built from repository
        # structure/metadata only, not from source lines, so there is nothing to
        # ground a real file:line citation against. Fabricating 1:1 placeholder
        # citations would misrepresent the answer as evidence-backed. Real
        # citations will come from the persisted knowledge graph (M2).
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
            citations=(),
        )
