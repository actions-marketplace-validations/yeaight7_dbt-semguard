from __future__ import annotations

import json
from typing import Any, Callable
from urllib import error, request


PR_COMMENT_MARKER = "<!-- dbt-semguard -->"

RequestFn = Callable[[str, str, str, dict[str, Any] | None], Any]


class GitHubRequestError(ValueError):
    def __init__(self, status_code: int, details: str):
        self.status_code = status_code
        self.details = details
        super().__init__(f"GitHub API request failed ({status_code}): {details}")


class GitHubPermissionError(GitHubRequestError):
    pass


def upsert_pr_comment(
    *,
    repo: str,
    pull_request_number: int,
    token: str,
    body: str,
    mode: str = "sticky",
    request: RequestFn | None = None,
) -> str:
    request_fn = request or _request_json
    comment_body = f"{PR_COMMENT_MARKER}\n{body}".strip()

    if mode == "create":
        request_fn(
            "POST",
            f"https://api.github.com/repos/{repo}/issues/{pull_request_number}/comments",
            token,
            {"body": comment_body},
        )
        return "created"

    comments = request_fn(
        "GET",
        f"https://api.github.com/repos/{repo}/issues/{pull_request_number}/comments?per_page=100",
        token,
        None,
    )
    existing = next((comment for comment in comments if PR_COMMENT_MARKER in comment.get("body", "")), None)
    if existing:
        request_fn(
            "PATCH",
            f"https://api.github.com/repos/{repo}/issues/comments/{existing['id']}",
            token,
            {"body": comment_body},
        )
        return "updated"

    request_fn(
        "POST",
        f"https://api.github.com/repos/{repo}/issues/{pull_request_number}/comments",
        token,
        {"body": comment_body},
    )
    return "created"


def _request_json(method: str, url: str, token: str, payload: dict[str, Any] | None) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    github_request = request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "dbt-semguard",
        },
    )
    try:
        with request.urlopen(github_request) as response:
            raw = response.read()
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        if exc.code in {401, 403}:
            raise GitHubPermissionError(exc.code, details) from exc
        raise GitHubRequestError(exc.code, details) from exc

    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))
