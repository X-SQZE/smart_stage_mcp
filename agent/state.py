from typing import List, TypedDict


class FileToWrite(TypedDict):
    path: str
    content: str


class AgentState(TypedDict):
    user_request: str
    repository_context: str
    relevant_files: List[str]
    architectural_plan: str
    scope_ok: bool
    clarifying_questions: List[str]
    branch_name: str
    commit_message: str
    pr_title: str
    pr_description: str
    files_to_write: List[FileToWrite]
    pull_request_url: str