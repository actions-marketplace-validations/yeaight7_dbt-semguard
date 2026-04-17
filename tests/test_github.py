from dbt_semguard.github import PR_COMMENT_MARKER, upsert_pr_comment


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
