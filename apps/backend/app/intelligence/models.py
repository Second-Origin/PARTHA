from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import CamelModel
from app.schemas.repository import RepositoryMeta

SourceRole = Literal[
    "entrypoint",
    "controller",
    "route",
    "service",
    "repository",
    "model",
    "dto",
    "interface",
    "enum",
    "utility",
    "configuration",
    "test",
    "documentation",
    "unknown",
]
SymbolKind = Literal["function", "class", "interface", "type", "enum", "constant", "route"]
GraphNodeType = Literal["repository", "module", "file", "symbol", "dependency"]
RelationshipType = Literal["imports", "calls", "extends", "implements", "depends_on", "contains", "references", "exports"]
DependencyType = Literal["production", "development", "peer", "optional"]


class RepositoryStatistics(CamelModel):
    total_files: int
    total_folders: int
    total_size: int
    source_files: int
    test_files: int
    config_files: int
    documentation_files: int


EnvironmentFileEvidenceClass = Literal["template_present", "runtime_env_file_present", "secret_like_value_detected"]


class EnvironmentFileEvidence(CamelModel):
    path: str
    evidence_class: EnvironmentFileEvidenceClass
    secret_keys: list[str] = Field(default_factory=list)


class RepositoryDiscovery(CamelModel):
    primary_language: str
    languages: dict[str, int]
    frameworks: list[str]
    package_managers: list[str]
    configuration_files: list[str]
    environment_files: list[str]
    environment_file_evidence: list[EnvironmentFileEvidence] = Field(default_factory=list)
    docker_files: list[str]
    ci_files: list[str]
    entry_points: list[str]
    build_systems: list[str]
    database_technologies: list[str]
    cloud_providers: list[str]
    statistics: RepositoryStatistics


class SourceSymbol(CamelModel):
    id: str
    name: str
    kind: SymbolKind
    file_path: str
    exported: bool = False


class SourceFileIntelligence(CamelModel):
    path: str
    name: str
    module_id: str
    language: str | None = None
    extension: str | None = None
    size: int = 0
    role: SourceRole = "unknown"
    imports: list[str] = []
    exports: list[str] = []
    api_routes: list[str] = []
    symbols: list[SourceSymbol] = []
    technologies: list[str] = []


class RepositoryModule(CamelModel):
    id: str
    name: str
    role: SourceRole
    layer: str
    path_prefix: str
    files: list[str]
    symbols: list[str]
    dependencies: list[str]


class RepositoryDependency(CamelModel):
    id: str
    name: str
    version: str
    type: DependencyType
    ecosystem: str
    source_file: str


class KnowledgeGraphNode(CamelModel):
    id: str
    type: GraphNodeType
    name: str
    path: str | None = None
    metadata: dict[str, object] = {}


class KnowledgeGraphRelationship(CamelModel):
    id: str
    source: str
    target: str
    type: RelationshipType
    evidence: list[str] = []


class KnowledgeGraph(CamelModel):
    nodes: list[KnowledgeGraphNode]
    relationships: list[KnowledgeGraphRelationship]


class RepositoryIntelligence(CamelModel):
    repository_id: str
    repository_name: str
    generated_at: datetime
    metadata: RepositoryMeta
    discovery: RepositoryDiscovery
    modules: list[RepositoryModule]
    files: list[SourceFileIntelligence]
    symbols: list[SourceSymbol]
    dependencies: list[RepositoryDependency]
    graph: KnowledgeGraph
