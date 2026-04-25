import json
import subprocess
import sys
from pathlib import Path

import pytest

from dbt_semguard import cli as cli_module
from dbt_semguard.github import GitHubPermissionError, GitHubRequestError


FIXTURES = Path(__file__).parent / "fixtures"


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "dbt_semguard.cli", *args]
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def test_extract_command_writes_contract_json(tmp_path: Path):
    output_path = tmp_path / "contract.json"

    result = run_cli(
        "extract",
        "--source",
        "yaml",
        "--project-dir",
        str(FIXTURES / "projects" / "base"),
        "--output",
        str(output_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text())
    assert payload["semantic_models"]["orders"]["model_name"] == "fct_orders"


def test_diff_command_renders_markdown():
    result = run_cli(
        "diff",
        "--base-contract",
        str(FIXTURES / "contracts" / "base_contract.json"),
        "--head-contract",
        str(FIXTURES / "contracts" / "base_contract.json"),
        "--format",
        "markdown",
    )

    assert result.returncode == 0, result.stderr
    assert "## dbt-semguard report" in result.stdout
    assert "No semantic changes detected." in result.stdout


def test_check_command_exits_nonzero_for_breaking_changes():
    result = run_cli(
        "check",
        "--base-contract",
        str(FIXTURES / "contracts" / "base_contract.json"),
        "--head-contract",
        str(FIXTURES / "contracts" / "breaking_contract.json"),
    )

    assert result.returncode == 1
    assert "Status: blocking" in result.stdout


def test_diff_command_renders_markdown_with_diagnostics(tmp_path: Path):
    repo = tmp_path / "tmp_cli_git_repo"
    repo.mkdir()
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)

    models_dir = repo / "models"
    models_dir.mkdir(exist_ok=True)
    (models_dir / "orders.yml").write_text((FIXTURES / "projects" / "base" / "models" / "orders.yml").read_text())
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "base"], repo)

    (models_dir / "orders.yml").write_text((FIXTURES / "projects" / "breaking_change" / "models" / "orders.yml").read_text())
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "head"], repo)

    base_ref = run(["git", "rev-parse", "HEAD~1"], repo).stdout.strip()
    head_ref = run(["git", "rev-parse", "HEAD"], repo).stdout.strip()

    result = run_cli(
        "diff",
        "--base-ref",
        base_ref,
        "--head-ref",
        head_ref,
        "--project-dir",
        str(repo),
        "--format",
        "markdown",
    )

    assert result.returncode == 0, result.stderr
    assert "Simple metric `gross_revenue` changed aggregation from `sum` to `avg`." in result.stdout
    assert "models/orders.yml:21" in result.stdout


def test_comment_pr_prefers_explicit_token_over_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_upsert_pr_comment(**kwargs):
        captured.update(kwargs)
        return "created"

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")
    monkeypatch.setenv("GITHUB_TOKEN", "github-env-token")
    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
            "--github-token",
            "flag-token",
        ]
    )

    assert result == 0
    assert captured["token"] == "flag-token"


def test_comment_pr_prefers_semguard_token_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_upsert_pr_comment(**kwargs):
        captured.update(kwargs)
        return "created"

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")
    monkeypatch.setenv("GITHUB_TOKEN", "github-env-token")
    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
        ]
    )

    assert result == 0
    assert captured["token"] == "semguard-env-token"


def test_comment_pr_falls_back_to_github_token_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_upsert_pr_comment(**kwargs):
        captured.update(kwargs)
        return "created"

    monkeypatch.delenv("SEMGUARD_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "github-env-token")
    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
        ]
    )

    assert result == 0
    assert captured["token"] == "github-env-token"


def test_comment_pr_errors_when_no_token_is_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")

    monkeypatch.delenv("SEMGUARD_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "GitHub token" in captured.err


def test_comment_pr_skips_permission_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")

    def fake_upsert_pr_comment(**kwargs):
        raise GitHubPermissionError(403, "forbidden")

    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
        ]
    )

    captured = capsys.readouterr()

    assert result == 0
    assert "skipping PR comment" in captured.err


def test_comment_pr_returns_error_for_non_permission_github_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    body_file = tmp_path / "body.md"
    body_file.write_text("hello", encoding="utf-8")

    monkeypatch.setenv("SEMGUARD_GITHUB_TOKEN", "semguard-env-token")

    def fake_upsert_pr_comment(**kwargs):
        raise GitHubRequestError(500, "server error")

    monkeypatch.setattr(cli_module, "upsert_pr_comment", fake_upsert_pr_comment)

    result = cli_module.main(
        [
            "comment-pr",
            "--body-file",
            str(body_file),
            "--repo",
            "yeaight7/dbt-semguard",
            "--pr-number",
            "12",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "server error" in captured.err
