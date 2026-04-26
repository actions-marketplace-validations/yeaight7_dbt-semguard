# Contributing

Thanks for contributing to `dbt-semguard`.

## Development Prerequisites

- Python 3.11 or newer
- Git

## Local Setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Running Tests

Run the full suite before opening a PR:

```bash
python -m pytest
```

Useful narrower checks while iterating:

```bash
python -m pytest tests/test_docs.py tests/test_release_surface.py tests/test_action_runner.py
python -m pytest tests/test_extractors.py
```

## Pull Requests

- keep changes scoped and intentional
- add or update tests for behavior changes
- update docs when CLI, action, or release behavior changes
- prefer small, reviewable commits with clear messages

## Reporting Security Issues

Please do not file public issues for vulnerabilities. Follow [SECURITY.md](SECURITY.md) instead.
