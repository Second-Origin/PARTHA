from app.ai.types import PromptBundle, RepositoryContext


class PromptBuilder:
    def build(self, repository_context: RepositoryContext, question: str) -> PromptBundle:
        repository_name = repository_context.repository.name
        context = self.render_repository_context(repository_context)
        return PromptBundle(
            system_prompt=(
                f"You are PARTHA's repository assistant for {repository_name}. "
                "Answer only from the provided repository context when possible. "
                "Mention relevant file paths explicitly and say when evidence is missing.\n\n"
                f"Repository context:\n{context}"
            ),
            user_prompt=question,
            metadata={"repositoryId": repository_context.repository.id},
        )

    def render_repository_context(self, repository_context: RepositoryContext) -> str:
        architecture = repository_context.architecture
        context_lines = [
            f"Primary language: {architecture.primary_language}",
            f"Frameworks: {', '.join(architecture.frameworks) if architecture.frameworks else 'Not detected'}",
            f"Entry points: {', '.join(architecture.entry_points) if architecture.entry_points else 'Not found'}",
            "Modules:",
            *[
                f"- {module.name} ({module.role}, {module.file_count} files)"
                for module in architecture.modules
            ],
            "Dependencies:",
            *[
                f"- {dependency.name} {dependency.version}"
                for dependency in repository_context.dependencies
            ],
            "Files:",
            *[f"- {file.path}" for file in repository_context.selected_files],
        ]
        return "\n".join(context_lines)
