from dbt_semguard.models import ChangeRecord, Report, SourceLocation
from dbt_semguard.reporting import render_report


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
