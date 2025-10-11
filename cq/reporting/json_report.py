"""JSON report writer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ..models import Report
from .schema import SCHEMA
from .validate import validate_dict


def write_json_report(report: Report, path: Path) -> None:
    data = serialize_report(report)
    validate_dict(data, SCHEMA)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def serialize_report(report: Report) -> Dict[str, Any]:
    project = report.project
    data = {
        "meta": report.meta,
        "project": {
            "path": project.path,
            "weights": project.weights,
            "role_weights": project.role_weights,
            "summary": {
                "duplication": project.summary.duplication,
                "lint": project.summary.lint,
                "typing": project.summary.typing,
                "complexity": project.summary.complexity,
                "grade": project.summary.grade,
            },
            "confidence": {
                "per_metric": project.confidence.per_metric,
                "intervals": project.confidence.intervals,
                "degraded": project.confidence.degraded,
            },
            "architecture": {"violations": project.architecture_violations},
        },
        "files": [
            {
                "path": file.path,
                "loc": file.loc,
                "role": file.role,
                "metrics": {
                    "duplication_ratio": file.metrics.duplication_ratio,
                    "lint": {
                        "C": file.metrics.lint_counts.get("C", 0),
                        "W": file.metrics.lint_counts.get("W", 0),
                        "R": file.metrics.lint_counts.get("R", 0),
                        "E": file.metrics.lint_counts.get("E", 0),
                        "weighted_score": file.metrics.lint_weighted_score,
                    },
                    "typing": {
                        "mypy_errors": file.metrics.typing_errors,
                        "annotation_coverage": file.metrics.annotation_coverage,
                        "score": file.metrics.typing_score,
                    },
                    "complexity": {
                        "cognitive": file.metrics.cognitive_complexity,
                        "per_loc": file.metrics.complexity_per_loc,
                        "score": file.metrics.complexity_score,
                    },
                },
                "grade": file.grade,
                "confidence": file.confidence,
                "missing_reasons": file.missing_reasons,
            }
            for file in report.files
        ],
    }
    return data

