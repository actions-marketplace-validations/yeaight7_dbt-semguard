from io import BytesIO
from urllib import error

import pytest

from dbt_semguard import github as github_module
from dbt_semguard.github import (
    GitHubPermissionError,
    GitHubRequestError,
    PR_COMMENT_MARKER,
    upsert_pr_comment,
)


def test_upsert_pr_comment_updates_existing_marker_comment():
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(method: str, url: str, token: str, payload: dict | None = None):
        calls.append((method, url, payload))
        if method == "GET":
            return [
                {"id": 1001, "body": f"{PR_COMMENT_MARKER}\nold body"},
                {"id": 1002, "body": "other comment"},
            ]
        if method == "PATCH":
            return {"id": 1001}
        raise AssertionError(f"unexpected request: {method} {url}")

    result = upsert_pr_comment(
        repo="yeaight7/dbt-semguard",
        pull_request_number=12,
        token="token",
        body="## dbt-semguard report\n\nStatus: passing",
        request=fake_request,
    )

    assert result == "updated"
    assert calls[0][0] == "GET"
    assert calls[1][0] == "PATCH"
    assert PR_COMMENT_MARKER in calls[1][2]["body"]


def test_upsert_pr_comment_creates_new_comment_when_missing_marker():
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(method: str, url: str, token: str, payload: dict | None = None):
        calls.append((method, url, payload))
        if method == "GET":
            return [{"id": 1002, "body": "other comment"}]
        if method == "POST":
            return {"id": 1003}
        raise AssertionError(f"unexpected request: {method} {url}")

    result = upsert_pr_comment(
        repo="yeaight7/dbt-semguard",
        pull_request_number=12,
        token="token",
        body="## dbt-semguard report\n\nStatus: passing",
        request=fake_request,
    )

    assert result == "created"
    assert calls[0][0] == "GET"
    assert calls[1][0] == "POST"
    assert PR_COMMENT_MARKER in calls[1][2]["body"]


def test_request_json_raises_permission_error_for_403(monkeypatch: pytest.MonkeyPatch):
    def fake_urlopen(_request):
        raise error.HTTPError(
            url="https://api.github.com/repos/yeaight7/dbt-semguard/issues/12/comments",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=BytesIO(b'{"message":"Resource not accessible by integration"}'),
        )

    monkeypatch.setattr(github_module.request, "urlopen", fake_urlopen)

    with pytest.raises(GitHubPermissionError, match="403"):
        github_module._request_json("GET", "https://api.github.com/test", "token", None)


def test_request_json_raises_request_error_for_non_permission_http_failures(monkeypatch: pytest.MonkeyPatch):
    def fake_urlopen(_request):
        raise error.HTTPError(
            url="https://api.github.com/repos/yeaight7/dbt-semguard/issues/12/comments",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=BytesIO(b'{"message":"Internal Server Error"}'),
        )

    monkeypatch.setattr(github_module.request, "urlopen", fake_urlopen)

    with pytest.raises(GitHubRequestError, match="500"):
        github_module._request_json("GET", "https://api.github.com/test", "token", None)
