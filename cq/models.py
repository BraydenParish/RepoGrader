"""Data models used within cq."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FileMetrics:
    duplication_ratio: float
    lint_counts: Dict[str, int]
    lint_weighted_score: float
    typing_errors: int
    typing_score: float
    annotation_coverage: float
    cognitive_complexity: int
    complexity_score: float
    complexity_per_loc: float


@dataclass
class FileReport:
    path: str
    loc: int
    role: str
    metrics: FileMetrics
    grade: float
    confidence: Dict[str, float]
    missing_reasons: List[str] = field(default_factory=list)


@dataclass
class ProjectSummary:
    duplication: float
    lint: float
    typing: float
    complexity: float
    grade: float


@dataclass
class ProjectConfidence:
    per_metric: Dict[str, float]
    intervals: Dict[str, List[float]]
    degraded: List[str]


@dataclass
class ProjectReport:
    path: str
    weights: Dict[str, Dict[str, float]]
    role_weights: Dict[str, float]
    summary: ProjectSummary
    confidence: ProjectConfidence
    architecture_violations: List[Dict[str, str]]


@dataclass
class Report:
    meta: Dict[str, object]
    project: ProjectReport
    files: List[FileReport]

