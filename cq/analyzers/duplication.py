"""Duplication analysis via winnowing."""
from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from ..config import DuplicationConfig
from ..utils.ast_tools import NormalizingTransformer, safe_parse


@dataclass
class DuplicationResult:
    fingerprints: Dict[str, List[int]]
    ratios: Dict[str, float]
    parser_success: Dict[str, bool]


class DuplicationAnalyzer:
    def __init__(self, config: DuplicationConfig) -> None:
        self.config = config

    def analyze(self, sources: Dict[str, str]) -> DuplicationResult:
        normalized: Dict[str, List[str]] = {}
        parser_success: Dict[str, bool] = {}
        for path, text in sources.items():
            norm_tokens, success = self._normalize(text)
            normalized[path] = norm_tokens
            parser_success[path] = success
        fingerprints = {
            path: self._fingerprints(tokens) for path, tokens in normalized.items()
        }
        ratios = self._compute_ratios(fingerprints)
        return DuplicationResult(fingerprints=fingerprints, ratios=ratios, parser_success=parser_success)

    def _normalize(self, text: str) -> Tuple[List[str], bool]:
        tree, success = safe_parse(text)
        if success and tree is not None and self.config.normalize.get("strip_literals", True):
            transformer = NormalizingTransformer(
                identifier_placeholder=str(
                    self.config.normalize.get("identifier_placeholder", "ID")
                )
            )
            tree = transformer.visit(tree)
            ast.fix_missing_locations(tree)
            normalized = ast.unparse(tree)
        else:
            normalized = text
        if self.config.normalize.get("strip_comments", True):
            normalized = self._strip_comments(normalized)
        tokens = normalized.split()
        return tokens, success

    def _strip_comments(self, text: str) -> str:
        lines = []
        for line in text.splitlines():
            if line.strip().startswith("#"):
                continue
            if "#" in line:
                idx = line.index("#")
                line = line[:idx]
            lines.append(line)
        return "\n".join(lines)

    def _fingerprints(self, tokens: Sequence[str]) -> List[int]:
        k = max(1, self.config.k)
        w = max(1, self.config.w)
        if len(tokens) < k:
            if not tokens:
                return []
            return [_stable_hash(" ".join(tokens))]
        hashes: List[int] = []
        window: List[Tuple[int, int]] = []  # (hash, position)
        min_hash = None
        min_pos = None
        for i in range(len(tokens) - k + 1):
            kgram = tokens[i : i + k]
            hash_val = _stable_hash(" ".join(kgram))
            window.append((hash_val, i))
            if len(window) > w:
                window.pop(0)
            current_min = min(window, key=lambda x: (x[0], x[1]))
            if (min_hash, min_pos) != current_min:
                min_hash, min_pos = current_min
                hashes.append(current_min[0])
        return hashes

    def _compute_ratios(self, fingerprints: Dict[str, List[int]]) -> Dict[str, float]:
        ratio: Dict[str, float] = {}
        items = list(fingerprints.items())
        for path, fprints in items:
            if not fprints:
                ratio[path] = 0.0
                continue
            overlaps = 0
            set_self = set(fprints)
            for other_path, other_fprints in items:
                if other_path == path:
                    continue
                overlaps += len(set_self.intersection(other_fprints))
            ratio[path] = min(1.0, overlaps / max(1, len(set_self)))
        return ratio


def _stable_hash(text: str) -> int:
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)

