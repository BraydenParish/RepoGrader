"""Schema validation helpers."""
from __future__ import annotations

from typing import Any, Dict

try:  # pragma: no cover - optional dependency
    from jsonschema import Draft202012Validator, ValidationError
except ImportError:  # pragma: no cover - fallback
    Draft202012Validator = None  # type: ignore
    ValidationError = Exception  # type: ignore

from ..models import Report
from .schema import SCHEMA


if Draft202012Validator is not None:
    _VALIDATOR = Draft202012Validator(SCHEMA)
else:  # pragma: no cover - fallback
    _VALIDATOR = None


def validate_dict(data: Dict[str, Any], schema: Dict[str, Any] | None = None) -> None:
    if Draft202012Validator is None:
        return
    validator = Draft202012Validator(schema or SCHEMA)
    validator.validate(data)


def validate_report(report: Report) -> None:
    data = {
        "meta": report.meta,
        "project": {
            "path": report.project.path,
            "weights": report.project.weights,
            "role_weights": report.project.role_weights,
            "summary": {
                "duplication": report.project.summary.duplication,
                "lint": report.project.summary.lint,
                "typing": report.project.summary.typing,
                "complexity": report.project.summary.complexity,
                "grade": report.project.summary.grade,
            },
            "confidence": {
                "per_metric": report.project.confidence.per_metric,
                "intervals": report.project.confidence.intervals,
                "degraded": report.project.confidence.degraded,
            },
            "architecture": {"violations": report.project.architecture_violations},
        },
        "files": [
            {
                "path": f.path,
                "loc": f.loc,
                "role": f.role,
                "metrics": {
                    "duplication_ratio": f.metrics.duplication_ratio,
                    "lint": {
                        "C": f.metrics.lint_counts.get("C", 0),
                        "W": f.metrics.lint_counts.get("W", 0),
                        "R": f.metrics.lint_counts.get("R", 0),
                        "E": f.metrics.lint_counts.get("E", 0),
                        "weighted_score": f.metrics.lint_weighted_score,
                    },
                    "typing": {
                        "mypy_errors": f.metrics.typing_errors,
                        "annotation_coverage": f.metrics.annotation_coverage,
                        "score": f.metrics.typing_score,
                    },
                    "complexity": {
                        "cognitive": f.metrics.cognitive_complexity,
                        "per_loc": f.metrics.complexity_per_loc,
                        "score": f.metrics.complexity_score,
                    },
                },
                "grade": f.grade,
                "confidence": f.confidence,
                "missing_reasons": f.missing_reasons,
            }
            for f in report.files
        ],
    }
    if _VALIDATOR is None:
        return
    try:
        _VALIDATOR.validate(data)
    except ValidationError as exc:  # pragma: no cover - defensive
        raise ValueError(str(exc))

