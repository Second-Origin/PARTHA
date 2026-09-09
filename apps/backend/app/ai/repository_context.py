from app.ai.types import (
    ArchitectureContext,
    DependencyContext,
    DocumentationContext,
    EngineeringReviewContext,
    ModuleContext,
    RepositoryContext,
    RepositoryIdentity,
    SelectedFileContext,
    SnapshotIdentity,
)
from app.core.exceptions import ValidationServiceError
from app.intelligence.query_service import SnapshotQueryService
from app.models.repository import RepositoryRecord


class RepositoryContextBuilder:
    def __init__(self, snapshots: SnapshotQueryService) -> None:
        self.snapshots = snapshots

    def build(self, record: RepositoryRecord, selected_file: str | None = None) -> RepositoryContext:
        projection = self.snapshots.product_projection(record.id)
        files = [file.path for file in projection.files]
        if selected_file is not None and selected_file not in files:
            raise ValidationServiceError(
                "The selected file is not present in the sealed snapshot.",
                {"selectedFile": selected_file, "snapshotId": projection.snapshot_id},
            )
        selected = [selected_file] if selected_file is not None else []
        highlighted = selected or files[:40]
        modules = tuple(
            ModuleContext(
                name=module.name,
                role=module.role,
                file_count=len(module.paths),
            )
            for module in projection.modules[:10]
        )
        dependencies: list[DependencyContext] = []
        for dependency in projection.dependencies[:20]:
            declared_versions = tuple(dict.fromkeys(declaration.version for declaration in dependency.declarations))
            has_conflict = len(declared_versions) > 1
            dependencies.append(
                DependencyContext(
                    name=dependency.name,
                    version=declared_versions[0] if len(declared_versions) == 1 else None,
                    declared_versions=declared_versions,
                    has_version_conflict=has_conflict,
                )
            )
        # The prompt contains structural facts, not source bytes. Even though
        # some snapshot facts have evidence spans, a provider answer cannot be
        # deterministically mapped back to them, so citations remain empty.
        return RepositoryContext(
            repository=RepositoryIdentity(id=record.id, name=record.name),
            snapshot=SnapshotIdentity(
                id=projection.snapshot_id,
                schema_version=projection.schema_version,
                revision_kind=projection.revision_kind,
                revision_value=projection.revision_value,
            ),
            architecture=ArchitectureContext(
                primary_language=projection.primary_language,
                frameworks=projection.frameworks,
                entry_points=projection.entry_points,
                modules=modules,
            ),
            dependencies=tuple(dependencies),
            documentation=DocumentationContext(files=tuple(highlighted)),
            engineering_review=EngineeringReviewContext(),
            selected_files=tuple(SelectedFileContext(path=path) for path in highlighted),
            citations=(),
        )
