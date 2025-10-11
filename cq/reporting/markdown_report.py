"""Markdown report rendering."""
from __future__ import annotations

from pathlib import Path
from typing import List

from ..models import Report


def write_markdown_report(report: Report, path: Path) -> None:
    md = render_markdown(report)
    path.write_text(md, encoding="utf-8")


def render_markdown(report: Report) -> str:
    project = report.project
    lines: List[str] = []
    lines.append(f"# Code Quotient Report")
    lines.append("")
    lines.append("## Project Summary")
    lines.append("")
    lines.append("| Metric | Score | Confidence |")
    lines.append("| --- | --- | --- |")
    per_metric = project.confidence.per_metric
    lines.append(
        f"| Duplication | {project.summary.duplication:.2f} | {per_metric.get('duplication', 0):.2f} |"
    )
    lines.append(f"| Lint | {project.summary.lint:.2f} | {per_metric.get('lint', 0):.2f} |")
    lines.append(
        f"| Typing | {project.summary.typing:.2f} | {per_metric.get('typing', 0):.2f} |"
    )
    lines.append(
        f"| Complexity | {project.summary.complexity:.2f} | {per_metric.get('complexity', 0):.2f} |"
    )
    interval = project.confidence.intervals.get("grade", [0.0, 0.0])
    lines.append(
        f"| Grade | {project.summary.grade:.2f} | CI: {interval[0]:.2f}-{interval[1]:.2f} |"
    )
    lines.append("")
    lines.append("## Architecture Violations")
    lines.append("")
    if project.architecture_violations:
        for violation in project.architecture_violations:
            lines.append(
                f"- `{violation['file']}`: {violation['from_layer']} -> {violation['to_layer']} via `{violation['import']}`"
            )
    else:
        lines.append("- None detected")
    lines.append("")
    files = sorted(report.files, key=lambda f: f.metrics.duplication_ratio, reverse=True)[:10]
    lines.append("## Top 10 Duplication")
    lines.append("")
    for file in files:
        lines.append(f"- `{file.path}` ({file.metrics.duplication_ratio:.2f})")
    lines.append("")
    lint_sorted = sorted(report.files, key=lambda f: f.metrics.lint_weighted_score)[:10]
    lines.append("## Top 10 Lint Findings")
    lines.append("")
    for file in lint_sorted:
        lines.append(
            f"- `{file.path}` (score {file.metrics.lint_weighted_score:.2f}, counts {file.metrics.lint_counts})"
        )
    lines.append("")
    complexity_sorted = sorted(report.files, key=lambda f: f.metrics.complexity_per_loc, reverse=True)[:10]
    lines.append("## Top 10 Cognitive Complexity")
    lines.append("")
    for file in complexity_sorted:
        lines.append(
            f"- `{file.path}` (complexity {file.metrics.cognitive_complexity}, per LOC {file.metrics.complexity_per_loc:.2f})"
        )
    lines.append("")
    lines.append("## Tools")
    lines.append("")
    for name, value in report.meta.get("tools", {}).items():
        lines.append(f"- {name}: {value}")
    lines.append("")
    return "\n".join(lines)

