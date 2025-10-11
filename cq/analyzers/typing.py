"""Typing analysis via mypy."""
from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from ..config import Config

MYPY_ERROR_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+): (?P<type>error|note): (?P<message>.+)$")


@dataclass
class TypingResult:
    errors: Dict[str, int]
    scores: Dict[str, float]
    coverage: Dict[str, float]
    degraded: bool
    missing_reason: str | None


class TypingAnalyzer:
    def __init__(self, config: Config) -> None:
        self.config = config

    def analyze(self, files: Iterable[str], loc_map: Dict[str, int], coverage: Dict[str, float]) -> TypingResult:
        cmd = [
            self.config.tools.mypy_cmd,
            "--hide-error-context",
            "--no-color-output",
            "--no-error-summary",
            "--show-error-codes",
            *files,
        ]
        errors: Dict[str, int] = defaultdict(int)
        degraded = False
        missing_reason: str | None = None
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                check=False,
                text=True,
                timeout=self.config.tools.timeouts.get("mypy", 120),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:  # pragma: no cover - error path
            degraded = True
            missing_reason = f"mypy unavailable: {exc}"
            return TypingResult(errors={}, scores={}, coverage=coverage, degraded=degraded, missing_reason=missing_reason)

        if completed.returncode not in (0, 1):
            degraded = True
            missing_reason = completed.stderr.strip() or "mypy run failed"
            return TypingResult(errors={}, scores={}, coverage=coverage, degraded=degraded, missing_reason=missing_reason)

        for line in completed.stdout.splitlines():
            match = MYPY_ERROR_RE.match(line)
            if match and match.group("type") == "error":
                path = match.group("path")
                errors[path] += 1

        scores: Dict[str, float] = {}
        for path, loc in loc_map.items():
            err_count = errors.get(path, 0)
            density = err_count * 1000 / max(1, loc)
            max_score = self.config.scoring.typing_error_scale.max_score_at_0
            zero_score_at = self.config.scoring.typing_error_scale.zero_score_at_20
            if density >= zero_score_at:
                score = 0.0
            else:
                score = max(0.0, max_score - (max_score / zero_score_at) * density)
            scores[path] = score
        return TypingResult(errors=dict(errors), scores=scores, coverage=coverage, degraded=degraded, missing_reason=missing_reason)

