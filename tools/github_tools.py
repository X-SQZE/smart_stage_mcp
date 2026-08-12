from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Any

import requests


DEFAULT_OWNER = os.getenv("GITHUB_OWNER")
DEFAULT_REPO = os.getenv("GITHUB_REPO")
TIMEOUT_SECONDS = 20
STATE_FILE = Path(__file__).resolve().parent.parent / ".active_repository"

_resource_cache: dict[str, str] = {}


def normalize_github_repo(github_repo: str | None = None) -> tuple[str, str]:
    if not github_repo:
        return _active_owner, _active_repo

    repo = github_repo.strip().removeprefix("https://github.com/").strip("/")
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Le repo doit etre au format 'owner/repo'.")
    return parts[0], parts[1]


def _load_active_repository() -> tuple[str, str]:
    if STATE_FILE.exists():
        saved_repo = STATE_FILE.read_text(encoding="utf-8").strip()
        if saved_repo:
            try:
                return normalize_github_repo(saved_repo)
            except ValueError:
                pass
    return DEFAULT_OWNER, DEFAULT_REPO


_active_owner, _active_repo = _load_active_repository()


def active_repo_full_name() -> str:
    return f"{_active_owner}/{_active_repo}"


def set_active_repository(github_repo: str) -> dict[str, str]:
    global _active_owner, _active_repo
    owner, repo = normalize_github_repo(github_repo)
    _active_owner, _active_repo = owner, repo
    STATE_FILE.write_text(active_repo_full_name(), encoding="utf-8")
    _resource_cache.clear()
    return {"status": "ok", "active_repository": active_repo_full_name()}

def list_commits(pr_number: int | None = None, branch: str | None = None, limit: int = 10) -> list[dict]:
    """
    Liste les commits récents.
    - Si pr_number est fourni : liste les commits de cette PR.
    - Sinon, si branch est fourni : liste les commits de cette branche.
    - Sinon : liste les commits de la branche par défaut du repo actif.
    """
    repo = get_active_repo()  # ta fonction existante qui retourne le repo GitHub actif
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    if pr_number is not None:
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/commits"
        params = {}
    else:
        url = f"https://api.github.com/repos/{repo}/commits"
        params = {"per_page": limit}
        if branch:
            params["sha"] = branch

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    commits_raw = response.json()

    commits = []
    for c in commits_raw[:limit]:
        commit_info = c.get("commit", {})
        commits.append({
            "sha": c["sha"][:7],
            "message": commit_info.get("message", "").split("\n")[0],
            "author": commit_info.get("author", {}).get("name"),
            "date": commit_info.get("author", {}).get("date"),
            "url": c.get("html_url"),
        })

    return commits
def get_active_repository() -> dict[str, str]:
    return {"active_repository": active_repo_full_name()}


def repo_api_url(github_repo: str | None = None) -> str:
    owner, repo = normalize_github_repo(github_repo)
    return f"https://api.github.com/repos/{owner}/{repo}"


def headers() -> dict[str, str]:
    request_headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    return request_headers


def github_error(response: requests.Response) -> dict[str, Any]:
    try:
        detail: Any = response.json()
    except ValueError:
        detail = response.text[:500]
    return {"error": "github_api_error", "status_code": response.status_code, "detail": detail}


def get(url: str, *, params: dict[str, Any] | None = None) -> requests.Response | dict[str, Any]:
    try:
        return requests.get(url, headers=headers(), params=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return {"error": "github_network_error", "detail": str(exc)}


def get_json(url: str, *, params: dict[str, Any] | None = None) -> Any:
    response = get(url, params=params)
    if isinstance(response, dict):
        return response
    if not response.ok:
        return github_error(response)
    try:
        return response.json()
    except ValueError:
        return {"error": "invalid_github_response"}


def post_json(url: str, payload: dict[str, Any]) -> Any:
    try:
        response = requests.post(url, headers=headers(), json=payload, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return {"error": "github_network_error", "detail": str(exc)}
    return response.json() if response.ok else github_error(response)


def put_json(url: str, payload: dict[str, Any]) -> Any:
    try:
        response = requests.put(url, headers=headers(), json=payload, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return {"error": "github_network_error", "detail": str(exc)}
    return response.json() if response.ok else github_error(response)


def paginated(url: str) -> list[Any] | dict[str, Any]:
    items: list[Any] = []
    for page in range(1, 11):
        data = get_json(url, params={"per_page": 100, "page": page})
        if isinstance(data, dict) and "error" in data:
            return data
        if not isinstance(data, list):
            return {"error": "unexpected_github_response", "detail": data}
        items.extend(data)
        if len(data) < 100:
            break
    return items


def fetch_github_doc(filepath: str) -> str:
    cache_key = f"{active_repo_full_name()}:{filepath}"
    if cache_key in _resource_cache:
        return _resource_cache[cache_key]

    data = get_json(f"{repo_api_url()}/contents/{filepath}")
    if isinstance(data, dict) and "error" in data:
        return f"# Erreur GitHub\n\nImpossible de recuperer `{filepath}` : `{data}`"
    if not isinstance(data, dict) or data.get("encoding") != "base64" or "content" not in data:
        return f"# Erreur\n\nLe fichier `{filepath}` n'est pas un fichier texte lisible."

    try:
        content = base64.b64decode(data["content"]).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        return f"# Erreur\n\nDecodage impossible de `{filepath}` : {exc}"

    _resource_cache[cache_key] = content
    return content


def get_pr_metadata(pr_number: int) -> dict[str, Any]:
    pr = get_json(f"{repo_api_url()}/pulls/{pr_number}")
    if isinstance(pr, dict) and "error" in pr:
        return pr
    return {
        "number": pr["number"],
        "title": pr["title"],
        "author": pr["user"]["login"],
        "target_branch": pr["base"]["ref"],
        "source_branch": pr["head"]["ref"],
        "head_sha": pr["head"]["sha"],
        "labels": [label["name"] for label in pr["labels"]],
        "state": pr["state"],
        "draft": pr["draft"],
    }


def get_repository_default_branch() -> str:
    data = get_json(repo_api_url())
    if isinstance(data, dict) and "error" not in data:
        return data.get("default_branch", "main")
    return "main"


def get_branch_head_sha(branch: str) -> str | dict[str, Any]:
    data = get_json(f"{repo_api_url()}/git/ref/heads/{branch}")
    if isinstance(data, dict) and "error" in data:
        return data
    return data["object"]["sha"]


def create_branch(branch_name: str, base_branch: str | None = None) -> dict[str, Any]:
    base = base_branch or get_repository_default_branch()
    base_sha = get_branch_head_sha(base)
    if isinstance(base_sha, dict):
        return base_sha

    existing = get_json(f"{repo_api_url()}/git/ref/heads/{branch_name}")
    if isinstance(existing, dict) and "error" not in existing:
        return {"status": "exists", "branch": branch_name, "sha": existing["object"]["sha"]}

    created = post_json(
        f"{repo_api_url()}/git/refs",
        {"ref": f"refs/heads/{branch_name}", "sha": base_sha},
    )
    if isinstance(created, dict) and "error" in created:
        return created
    return {"status": "created", "branch": branch_name, "sha": created["object"]["sha"]}


def upsert_file(path: str, content: str, branch: str, message: str) -> dict[str, Any]:
    current = get_json(f"{repo_api_url()}/contents/{path}", params={"ref": branch})
    payload: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if isinstance(current, dict) and "error" not in current and current.get("sha"):
        payload["sha"] = current["sha"]
    result = put_json(f"{repo_api_url()}/contents/{path}", payload)
    if isinstance(result, dict) and "error" in result:
        return result
    return {"status": "committed", "path": path, "commit": result.get("commit", {})}


def create_pull_request(title: str, body: str, head: str, base: str | None = None) -> dict[str, Any]:
    target_base = base or get_repository_default_branch()
    result = post_json(
        f"{repo_api_url()}/pulls",
        {"title": title, "body": body, "head": head, "base": target_base},
    )
    if isinstance(result, dict) and "error" in result:
        return result
    return {
        "number": result["number"],
        "title": result["title"],
        "url": result["html_url"],
        "head": head,
        "base": target_base,
    }


def list_pr_comments(pr_number: int) -> dict[str, Any]:
    discussion_comments = paginated(f"{repo_api_url()}/issues/{pr_number}/comments")
    if isinstance(discussion_comments, dict):
        return discussion_comments
    review_comments = paginated(f"{repo_api_url()}/pulls/{pr_number}/comments")
    if isinstance(review_comments, dict):
        return review_comments
    return {
        "pr_number": pr_number,
        "discussion_comments": discussion_comments,
        "review_comments": review_comments,
        "total_count": len(discussion_comments) + len(review_comments),
    }


def list_pr_reviews(pr_number: int) -> list[Any] | dict[str, Any]:
    return paginated(f"{repo_api_url()}/pulls/{pr_number}/reviews")


def get_file_changes(pr_number: int, filepath: str) -> dict[str, Any]:
    files = paginated(f"{repo_api_url()}/pulls/{pr_number}/files")
    if isinstance(files, dict):
        return files
    return next((file for file in files if file["filename"] == filepath), {"error": "file_not_found"})


def list_pr_files(pr_number: int) -> list[dict[str, Any]] | dict[str, Any]:
    files = paginated(f"{repo_api_url()}/pulls/{pr_number}/files")
    if isinstance(files, dict):
        return files
    return [
        {
            "path": file["filename"],
            "status": file["status"],
            "additions": file["additions"],
            "deletions": file["deletions"],
            "changes": file["changes"],
            "previous_path": file.get("previous_filename"),
            "patch": file.get("patch"),
        }
        for file in files
    ]


def list_repository_tree(ref: str = "main", path_prefix: str = "") -> list[dict[str, Any]] | dict[str, Any]:
    data = get_json(f"{repo_api_url()}/git/trees/{ref}", params={"recursive": "1"})
    if isinstance(data, dict) and "error" in data:
        return data
    if not isinstance(data, dict) or "tree" not in data:
        return {"error": "unexpected_github_response", "detail": data}

    prefix = path_prefix.strip("/")
    if prefix:
        prefix = f"{prefix}/"
    entries = [
        {"path": item["path"], "type": item["type"], "size": item.get("size"), "sha": item["sha"]}
        for item in data["tree"]
        if not prefix or item["path"].startswith(prefix)
    ]
    return {"ref": ref, "path_prefix": path_prefix, "truncated": data.get("truncated", False), "entries": entries}


def check_merge_conflicts(pr_number: int) -> dict[str, Any]:
    pr = get_json(f"{repo_api_url()}/pulls/{pr_number}")
    if isinstance(pr, dict) and "error" in pr:
        return pr
    return {"mergeable": pr.get("mergeable"), "mergeable_state": pr.get("mergeable_state")}


def get_ci_status(pr_number: int) -> dict[str, Any]:
    pr = get_json(f"{repo_api_url()}/pulls/{pr_number}")
    if isinstance(pr, dict) and "error" in pr:
        return pr
    sha = pr["head"]["sha"]
    checks = get_json(f"{repo_api_url()}/commits/{sha}/check-runs", params={"per_page": 100})
    if isinstance(checks, dict) and "error" in checks:
        return checks
    return {
        "head_sha": sha,
        "status": checks.get("status"),
        "conclusion": checks.get("conclusion"),
        "total_count": checks.get("total_count", 0),
        "check_runs": checks.get("check_runs", []),
    }


def post_pr_comment(pr_number: int, message: str) -> dict[str, Any]:
    if not message.strip():
        return {"error": "empty_comment"}
    try:
        response = requests.post(
            f"{repo_api_url()}/issues/{pr_number}/comments",
            headers=headers(),
            json={"body": message},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return {"error": "github_network_error", "detail": str(exc)}
    return response.json() if response.ok else github_error(response)


def detect_breaking_changes(pr_number: int) -> dict[str, Any]:
    files = paginated(f"{repo_api_url()}/pulls/{pr_number}/files")
    if isinstance(files, dict):
        return files

    results: list[dict[str, Any]] = []
    for file in files:
        if not file["filename"].endswith((".py", ".js", ".ts")):
            continue
        removed = re.findall(r"^-.*?\b(?:def|function)\s+(\w+)\s*\(", file.get("patch", ""), re.MULTILINE)
        for name in set(removed):
            data = get_json(
                "https://api.github.com/search/code",
                params={"q": f"{name} repo:{active_repo_full_name()}"},
            )
            if isinstance(data, dict) and "error" not in data:
                paths = [item["path"] for item in data.get("items", []) if item["path"] != file["filename"]]
                if paths:
                    results.append({
                        "function": name,
                        "modified_in": file["filename"],
                        "still_referenced_in": paths,
                        "risk": "eleve : usages potentiellement casses",
                    })
    return {"status": "warning", "breaking_changes": results} if results else {"status": "ok", "message": "Aucun breaking change detecte"}


def guide_contributor(intent: str) -> dict[str, Any]:
    stopwords = {
        "je", "veux", "comment", "ou", "est", "le", "la", "les", "un", "une",
        "de", "du", "des", "pour", "dans", "sur", "add", "want", "how", "the",
    }
    keywords = [word.lower() for word in re.findall(r"\w+", intent) if len(word) > 2 and word.lower() not in stopwords]
    findings: list[dict[str, str]] = []
    search_errors: list[dict[str, Any]] = []

    for keyword in keywords[:5]:
        data = get_json(
            "https://api.github.com/search/code",
            params={"q": f"{keyword} repo:{active_repo_full_name()}", "per_page": 5},
        )
        if isinstance(data, dict) and "error" not in data:
            findings.extend({
                "keyword_matched": keyword,
                "file": item["path"],
                "url": item.get("html_url", ""),
                "source": "code_search",
            } for item in data.get("items", []))
        elif isinstance(data, dict):
            search_errors.append({"keyword": keyword, "error": data.get("error"), "status_code": data.get("status_code")})

    if not findings:
        repository = get_json(repo_api_url())
        default_branch = repository.get("default_branch", "main") if isinstance(repository, dict) else "main"
        tree = get_json(f"{repo_api_url()}/git/trees/{default_branch}", params={"recursive": "1"})
        if isinstance(tree, dict) and "tree" in tree:
            for keyword in keywords[:5]:
                for item in tree["tree"]:
                    path = item["path"]
                    if item["type"] == "blob" and keyword in path.lower():
                        findings.append({
                            "keyword_matched": keyword,
                            "file": path,
                            "url": f"https://github.com/{active_repo_full_name()}/blob/{default_branch}/{path}",
                            "source": "repository_tree",
                        })

    unique = list({item["file"]: item for item in findings}.values())
    return {
        "intent": intent,
        "relevant_files": unique or "Aucun fichier trouve. Verifiez le token GitHub ou reformulez l'intention.",
        "search_errors": search_errors,
        "next_step": "Consultez elyora://docs/manifest puis elyora://docs/architecture avant de modifier le code.",
    }
def list_prs(state: str = "open", repo: str = "") -> str:
    """Liste les Pull Requests d'un dépôt GitHub.

    Args:
        state: "open", "closed" ou "all" (défaut: "open")
        repo: "owner/repo" — si vide, utilise le dépôt actif
    """
    try:
        base_url = repo_api_url(repo or None)
    except ValueError as exc:
        return f"Erreur : {exc}"

    prs = paginated(f"{base_url}/pulls?state={state}")
    if isinstance(prs, dict) and "error" in prs:
        return f"Erreur : {prs}"

    if not prs:
        target = repo or active_repo_full_name()
        return f"Aucune PR trouvée (état: {state}) sur {target}."

    return "\n".join(
        f"#{pr['number']} [{'merged' if pr.get('merged_at') else pr['state']}] "
        f"{pr['title']} — {pr['user']['login']} — {pr['html_url']}"
        for pr in prs
    )