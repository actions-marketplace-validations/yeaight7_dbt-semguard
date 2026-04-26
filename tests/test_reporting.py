import json

import pytest

from dbt_semguard.models import ChangeRecord, Report, Severity, SourceLocation
from dbt_semguard.reporting import build_report, render_report


def test_markdown_report_includes_source_location_suffix():
    report = Report(
        summary={"breaking": 1, "risky": 0, "safe": 0},
        highest_severity="breaking",
        blocking=True,
        changes=[
            ChangeRecord(
                code="metric.simple.agg_changed",
                severity="breaking",
                message="Metric `gross_revenue` changed aggregation from `sum` to `avg`.",
                path="metrics.gross_revenue",
                source=SourceLocation(file="models/orders.yml", line=24),
            )
        ],
        metadata={},
    )

    rendered = render_report(report, "markdown")

    assert "- Metric `gross_revenue` changed aggregation from `sum` to `avg`. (`models/orders.yml:24`)" in rendered


def test_markdown_groups_multiple_changes_for_same_object():
    report = Report(
        summary={"breaking": 2, "risky": 0, "safe": 0},
        highest_severity="breaking",
        blocking=True,
        changes=[
            ChangeRecord(
                code="metric.simple.agg_changed",
                severity="breaking",
                message="Metric `gross_revenue` changed aggregation from `sum` to `avg`.",
                path="metrics.gross_revenue",
            ),
            ChangeRecord(
                code="metric.simple.expr_changed",
                severity="breaking",
                message="Metric `gross_revenue` changed expression from `order_total` to `net_revenue`.",
                path="metrics.gross_revenue",
            ),
        ],
        metadata={},
    )

    rendered = render_report(report, "markdown")

    assert "#### Metric `gross_revenue`" in rendered
    assert "- Metric `gross_revenue` changed aggregation from `sum` to `avg`." in rendered
    assert "- Metric `gross_revenue` changed expression from `order_total` to `net_revenue`." in rendered


def test_severity_enum_serializes_as_existing_json_strings():
    report = Report(
        summary={"breaking": 1, "risky": 0, "safe": 0},
        highest_severity=Severity.BREAKING,
        blocking=True,
        changes=[
            ChangeRecord(
                code="metric.simple.agg_changed",
                severity=Severity.BREAKING,
                message="Metric changed.",
                path="metrics.gross_revenue",
            )
        ],
    )

    payload = report.model_dump()
    assert payload["highest_severity"] == "breaking"
    assert payload["changes"][0]["severity"] == "breaking"
    assert json.loads(json.dumps(payload))["changes"][0]["severity"] == "breaking"


def test_unknown_change_severity_fails_clearly():
    change = ChangeRecord(
        code="metric.simple.agg_changed",
        severity="catastrophic",
        message="Metric changed.",
        path="metrics.gross_revenue",
    )

    with pytest.raises(ValueError, match="Unknown severity 'catastrophic'"):
        build_report([change])
