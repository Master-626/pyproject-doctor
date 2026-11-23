"""Human-readable and JSON reports."""

from __future__ import annotations

import json

from pyproject_doctor.checks import Report


def render_text(report: Report) -> str:
    lines = ["Target: %s" % report.target, ""]
    rows = [("STATUS", "CHECK", "DETAIL")]
    for item in report.checks:
        rows.append((item.status, item.name, item.detail))
    widths = [
        max(len(row[0]) for row in rows),
        max(len(row[1]) for row in rows),
        max(len(row[2]) for row in rows),
    ]
    header = "  %s  %s  %s" % (
        rows[0][0].ljust(widths[0]),
        rows[0][1].ljust(widths[1]),
        rows[0][2].ljust(widths[2]),
    )
    rule = "  %s  %s  %s" % (
        "-" * widths[0],
        "-" * widths[1],
        "-" * widths[2],
    )
    lines.append(header)
    lines.append(rule)
    for row in rows[1:]:
        lines.append(
            "  %s  %s  %s"
            % (row[0].ljust(widths[0]), row[1].ljust(widths[1]), row[2])
        )
    lines.append("")
    lines.append("%s passed, %s failed" % (report.passed, report.failed))
    fixes = [item for item in report.checks if item.fix]
    if fixes:
        lines.append("")
        lines.append("Suggested fixes:")
        for item in fixes:
            lines.append("  %-10s  %s" % (item.id, item.fix))
    lines.append("")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=False) + "\n"
