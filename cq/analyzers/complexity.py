"""Cognitive complexity computation."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

from ..config import Config
from ..utils.ast_tools import safe_parse


@dataclass
class ComplexityResult:
    scores: Dict[str, float]
    raw: Dict[str, int]
    per_loc: Dict[str, float]


class ComplexityAnalyzer:
    """Compute Sonar-style cognitive complexity.

    We increment by 1 for each control structure (if/elif/for/while/try/except/finally/with), add nesting
    penalties proportional to the depth, count boolean operators beyond the first, and count early returns.
    The score is normalized per LOC against a target scale defined in the configuration.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def analyze(self, sources: Dict[str, str], loc_map: Dict[str, int]) -> ComplexityResult:
        scores: Dict[str, float] = {}
        raw: Dict[str, int] = {}
        per_loc: Dict[str, float] = {}
        for path, source in sources.items():
            tree, success = safe_parse(source)
            if not success or tree is None:
                raw[path] = 0
                per_loc[path] = 0.0
                scores[path] = 100.0
                continue
            complexity = self._compute(tree)
            raw[path] = complexity
            loc = max(1, loc_map.get(path, 1))
            per = complexity / loc
            per_loc[path] = per
            target = self.config.scoring.complexity_scale.target_per_loc
            hard_cap = self.config.scoring.complexity_scale.hard_cap
            if complexity >= hard_cap:
                score = 0.0
            else:
                ratio = min(1.0, per / max(target, 1e-6))
                score = max(0.0, 100.0 * (1 - ratio))
            scores[path] = score
        return ComplexityResult(scores=scores, raw=raw, per_loc=per_loc)

    def _compute(self, tree: ast.AST) -> int:
        complexity = 0
        stack: list[int] = []

        def enter(extra: int = 1) -> None:
            nonlocal complexity
            complexity += extra + len(stack)
            stack.append(1)

        def leave() -> None:
            if stack:
                stack.pop()

        class Visitor(ast.NodeVisitor):
            def visit_If(self, node: ast.If) -> None:  # noqa: N802
                enter()
                for idx, test in enumerate(node.orelse):
                    if isinstance(test, ast.If):
                        enter()
                        self.generic_visit(test)
                        leave()
                self.generic_visit(node.test)
                for child in node.body:
                    self.visit(child)
                for child in node.orelse:
                    if not isinstance(child, ast.If):
                        self.visit(child)
                leave()

            def visit_For(self, node: ast.For) -> None:  # noqa: N802
                enter()
                self.generic_visit(node)
                leave()

            visit_AsyncFor = visit_For  # type: ignore

            def visit_While(self, node: ast.While) -> None:  # noqa: N802
                enter()
                self.generic_visit(node)
                leave()

            def visit_With(self, node: ast.With) -> None:  # noqa: N802
                enter()
                self.generic_visit(node)
                leave()

            visit_AsyncWith = visit_With  # type: ignore

            def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
                enter()
                for handler in node.handlers:
                    enter()
                    self.generic_visit(handler)
                    leave()
                if node.finalbody:
                    enter()
                    for child in node.finalbody:
                        self.visit(child)
                    leave()
                for child in node.body:
                    self.visit(child)
                for child in node.orelse:
                    self.visit(child)
                leave()

            def visit_BoolOp(self, node: ast.BoolOp) -> None:  # noqa: N802
                nonlocal complexity
                complexity += max(0, len(node.values) - 1)
                self.generic_visit(node)

            def visit_Return(self, node: ast.Return) -> None:  # noqa: N802
                nonlocal complexity
                complexity += 1
                self.generic_visit(node)

        Visitor().visit(tree)
        stack.clear()
        return complexity

