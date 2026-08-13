from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Entrée utilisateur
    user_request: str

    # Repository / RAG
    repository_context: str
    relevant_files: list[str]

    # Analyse / planification
    architectural_plan: str

    # Validation
    scope_ok: bool
    clarifying_questions: list[str]

    # Git / implémentation
    branch_name: str
    commit_message: str
    files_to_write: list[dict]

    # Pull Request
    pr_title: str
    pr_description: str
    pull_request_url: str