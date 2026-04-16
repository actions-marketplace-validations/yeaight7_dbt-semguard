from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_action_installs_from_action_path_and_has_branding():
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))

    assert action["branding"] == {"icon": "shield", "color": "blue"}
    install_step = next(step for step in action["runs"]["steps"] if step.get("name") == "Install dbt-semguard")
    assert '${{ github.action_path }}' in install_step["run"]
    assert "python -m pip install ." not in install_step["run"]


def test_readme_uses_marketplace_action_ref_and_relative_links():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "- uses: yeaight7/dbt-semguard@v0.1.1" in readme
    assert "uses: ./" not in readme
    assert "C:/Users/Rivero/" not in readme
    assert "(docs/contract-spec.md)" in readme
    assert "(examples/ecommerce_dbt_project)" in readme
