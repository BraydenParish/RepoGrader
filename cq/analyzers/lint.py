"""Lint analysis using pylint."""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from ..config import Config


@dataclass
class LintResult:
    counts: Dict[str, Dict[str, int]]
    weighted_scores: Dict[str, float]
    degraded: bool
    missing_reason: str | None


class LintAnalyzer:
    def __init__(self, config: Config) -> None:
        self.config = config

    def analyze(self, files: Iterable[str]) -> LintResult:
        pylint_cmd = [self.config.tools.pylint_cmd, "--output-format=json", *files]
        counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"C": 0, "W": 0, "R": 0, "E": 0})
        weighted_scores: Dict[str, float] = {}
        degraded = False
        missing_reason: str | None = None
        try:
            completed = subprocess.run(
                pylint_cmd,
                capture_output=True,
                check=False,
                text=True,
                timeout=self.config.tools.timeouts.get("pylint", 90),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover - error path
            degraded = True
            missing_reason = f"pylint unavailable: {exc}"
            return LintResult(counts={}, weighted_scores={}, degraded=degraded, missing_reason=missing_reason)

        if completed.returncode not in (0, 2, 4, 8, 16, 32):
            degraded = True
            missing_reason = completed.stderr.strip() or "pylint run failed"
            return LintResult(counts={}, weighted_scores={}, degraded=degraded, missing_reason=missing_reason)

        try:
            messages = json.loads(completed.stdout or "[]")
        except json.JSONDecodeError:
            degraded = True
            missing_reason = "pylint produced invalid JSON"
            return LintResult(counts={}, weighted_scores={}, degraded=degraded, missing_reason=missing_reason)

        for message in messages:
            path = message.get("path")
            msg_id = message.get("symbol") or ""
            category = msg_id[:1].upper() if msg_id else message.get("type", "").upper()[:1]
            if category not in counts[path]:
                counts[path][category] = 0
            counts[path][category] += 1

        weights = self.config.weights["pylint_categories"]
        for path, cat_counts in counts.items():
            total = 0.0
            for cat, count in cat_counts.items():
                weight = weights.get(cat, 0.0)
                total += weight * count
            weighted_scores[path] = max(0.0, 100.0 - total)
        return LintResult(counts=dict(counts), weighted_scores=weighted_scores, degraded=degraded, missing_reason=missing_reason)

