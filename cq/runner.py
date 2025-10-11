"""Main runner orchestrating analysis."""
from __future__ import annotations

import math
import platform
import statistics
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from typing import Dict, Iterable, List, Tuple

from .analyzers.architecture import ArchitectureAnalyzer
from .analyzers.complexity import ComplexityAnalyzer
from .analyzers.duplication import DuplicationAnalyzer
from .analyzers.lint import LintAnalyzer
from .analyzers.typing import TypingAnalyzer
from .config import Config
from .models import FileMetrics, FileReport, ProjectConfidence, ProjectReport, ProjectSummary, Report
from .reporting.validate import validate_report
from .utils import fs
from .utils.ast_tools import count_annotation_coverage, safe_parse


class Runner:
    def __init__(self, config: Config) -> None:
        self.config = config

    def run(self, root_path: Path) -> Tuple[Report, List[str]]:
        include = [str(root_path / Path(p)) for p in self.config.paths.include]
        exclude = [str(root_path / Path(p)) for p in self.config.paths.exclude]
        files = sorted(fs.iter_python_files(include, exclude))
        sources: Dict[str, str] = {}
        loc_map: Dict[str, int] = {}
        roles: Dict[str, str] = {}
        coverage_ratio: Dict[str, float] = {}
        parser_success: Dict[str, bool] = {}
        for path in files:
            text, loc = fs.read_text(path)
            rel_path = str(path.relative_to(root_path))
            sources[rel_path] = text
            loc_map[rel_path] = loc
            roles[rel_path] = fs.detect_role(path)
            tree, success = safe_parse(text)
            parser_success[rel_path] = success
            if tree is not None and success:
                annotated, total = count_annotation_coverage(tree)
                coverage_ratio[rel_path] = annotated / total if total else 0.0
            else:
                coverage_ratio[rel_path] = 0.0

        duplication = DuplicationAnalyzer(self.config.duplication).analyze(sources)
        architecture = ArchitectureAnalyzer(self.config.arch).analyze(sources)
        complexity = ComplexityAnalyzer(self.config).analyze(sources, loc_map)

        lint = LintAnalyzer(self.config).analyze([str(root_path / f) for f in sources.keys()])
        typing = TypingAnalyzer(self.config).analyze(
            [str(root_path / f) for f in sources.keys()], loc_map, coverage_ratio
        )

        files_report: List[FileReport] = []
        weights = self.config.weights["metrics"]
        degraded_metrics: set[str] = set()
        for rel_path, loc in loc_map.items():
            missing: List[str] = []
            lint_counts = lint.counts.get(str(root_path / rel_path), {"C": 0, "W": 0, "R": 0, "E": 0})
            lint_score = lint.weighted_scores.get(str(root_path / rel_path), 100.0)
            lint_conf = 0.4 if lint.degraded else 1.0
            if lint.degraded:
                degraded_metrics.add("lint")
                missing.append(lint.missing_reason or "pylint degraded")
            typing_errors = typing.errors.get(str(root_path / rel_path), 0)
            typing_score = typing.scores.get(str(root_path / rel_path), 100.0)
            typing_conf = 0.4 if typing.degraded else 1.0
            if typing.degraded:
                degraded_metrics.add("typing")
                missing.append(typing.missing_reason or "mypy degraded")
            duplication_ratio = duplication.ratios.get(rel_path, 0.0)
            duplication_conf = 1.0 if duplication.parser_success.get(rel_path, False) else 0.5
            complexity_score = complexity.scores.get(rel_path, 100.0)
            complexity_raw = complexity.raw.get(rel_path, 0)
            complexity_per_loc = complexity.per_loc.get(rel_path, 0.0)
            complexity_conf = 1.0 if parser_success.get(rel_path, False) else 0.5
            base_conf = min(1.0, math.log1p(loc) / math.log1p(300))
            base_conf *= 1.0 if parser_success.get(rel_path, False) else 0.6
            file_conf = {
                "duplication": base_conf * duplication_conf,
                "lint": base_conf * lint_conf,
                "typing": base_conf * typing_conf,
                "complexity": base_conf * complexity_conf,
            }
            overall_conf = min(1.0, statistics.mean(file_conf.values()))
            file_conf["overall"] = overall_conf
            metrics = FileMetrics(
                duplication_ratio=duplication_ratio,
                lint_counts=lint_counts,
                lint_weighted_score=lint_score,
                typing_errors=typing_errors,
                typing_score=typing_score,
                annotation_coverage=coverage_ratio.get(rel_path, 0.0),
                cognitive_complexity=complexity_raw,
                complexity_score=complexity_score,
                complexity_per_loc=complexity_per_loc,
            )
            grade = _weighted_grade(
                metrics,
                weights,
            )
            files_report.append(
                FileReport(
                    path=rel_path,
                    loc=loc,
                    role=roles.get(rel_path, "default"),
                    metrics=metrics,
                    grade=grade,
                    confidence=file_conf,
                    missing_reasons=missing,
                )
            )

        role_weights = self.config.weights["roles"]
        project_metrics = _aggregate_project(files_report, role_weights)
        bootstrap_interval = _bootstrap_interval(
            [f.grade for f in files_report],
            self.config.bootstrap.iterations,
            self.config.bootstrap.seed,
        )
        project_confidence = ProjectConfidence(
            per_metric={
                "duplication": statistics.mean(f.confidence["duplication"] for f in files_report)
                if files_report
                else 0.0,
                "lint": statistics.mean(f.confidence["lint"] for f in files_report) if files_report else 0.0,
                "typing": statistics.mean(f.confidence["typing"] for f in files_report)
                if files_report
                else 0.0,
                "complexity": statistics.mean(f.confidence["complexity"] for f in files_report)
                if files_report
                else 0.0,
            },
            intervals={"grade": bootstrap_interval},
            degraded=sorted(degraded_metrics),
        )

        project_report = ProjectReport(
            path=str(root_path),
            weights=self.config.weights,
            role_weights=role_weights,
            summary=ProjectSummary(
                duplication=project_metrics["duplication"],
                lint=project_metrics["lint"],
                typing=project_metrics["typing"],
                complexity=project_metrics["complexity"],
                grade=project_metrics["grade"],
            ),
            confidence=project_confidence,
            architecture_violations=[
                {
                    "file": v.file,
                    "from_layer": v.from_layer,
                    "to_layer": v.to_layer,
                    "import": v.import_name,
                }
                for v in architecture
            ],
        )

        report = Report(
            meta={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "cq_version": "0.1.0",
                "tools": {
                    "python": platform.python_version(),
                    "pylint": self.config.tools.pylint_cmd,
                    "mypy": self.config.tools.mypy_cmd,
                },
            },
            project=project_report,
            files=files_report,
        )
        errors: List[str] = []
        try:
            validate_report(report)
        except ValueError as exc:  # pragma: no cover - defensive
            errors.append(str(exc))
        return report, errors


def _weighted_grade(metrics: FileMetrics, weights: Dict[str, float]) -> float:
    return sum(
        [
            (1 - metrics.duplication_ratio) * weights.get("duplication", 0.0) * 100,
            metrics.lint_weighted_score * weights.get("lint", 0.0),
            metrics.typing_score * weights.get("typing", 0.0),
            metrics.complexity_score * weights.get("complexity", 0.0),
        ]
    ) / max(1e-6, sum(weights.values()))


def _aggregate_project(files: List[FileReport], role_weights: Dict[str, float]) -> Dict[str, float]:
    totals = {"duplication": 0.0, "lint": 0.0, "typing": 0.0, "complexity": 0.0, "grade": 0.0}
    weight_totals = {key: 0.0 for key in totals.keys()}
    for file_report in files:
        role_weight = role_weights.get(file_report.role, role_weights.get("default", 1.0))
        factor = role_weight * file_report.loc
        totals["duplication"] += (1 - file_report.metrics.duplication_ratio) * factor * 100
        totals["lint"] += file_report.metrics.lint_weighted_score * factor
        totals["typing"] += file_report.metrics.typing_score * factor
        totals["complexity"] += file_report.metrics.complexity_score * factor
        totals["grade"] += file_report.grade * factor
        for key in weight_totals.keys():
            weight_totals[key] += factor
    return {
        key: (totals[key] / max(1e-6, weight_totals[key])) if weight_totals[key] else 0.0
        for key in totals.keys()
    }


def _bootstrap_interval(values: List[float], iterations: int, seed: int) -> List[float]:
    if not values:
        return [0.0, 0.0]
    rng = Random(seed)
    samples = []
    for _ in range(iterations):
        sample = [rng.choice(values) for _ in values]
        samples.append(statistics.mean(sample))
    samples.sort()
    n = len(samples)
    lower_idx = max(0, int(0.05 * (n - 1)))
    upper_idx = min(n - 1, int(0.95 * (n - 1)))
    lower = samples[lower_idx]
    upper = samples[upper_idx]
    return [lower, upper]


