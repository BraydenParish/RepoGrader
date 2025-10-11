"""AST utilities for cq."""
from __future__ import annotations

import ast
from typing import Iterable, List, Tuple


class NormalizingTransformer(ast.NodeTransformer):
    """Normalize identifiers and literals for duplication detection."""

    def __init__(self, identifier_placeholder: str = "ID") -> None:
        self.identifier_placeholder = identifier_placeholder

    def visit_Name(self, node: ast.Name) -> ast.AST:  # noqa: N802
        return ast.copy_location(ast.Name(id=self.identifier_placeholder, ctx=node.ctx), node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:  # noqa: N802
        new_node = ast.Attribute(
            value=self.visit(node.value),
            attr=self.identifier_placeholder,
            ctx=node.ctx,
        )
        return ast.copy_location(new_node, node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:  # noqa: N802
        return ast.copy_location(ast.Constant(value="CONST"), node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:  # noqa: N802
        node.name = self.identifier_placeholder
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:  # noqa: N802
        node.name = self.identifier_placeholder
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:  # noqa: N802
        node.name = self.identifier_placeholder
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:  # noqa: N802
        node.arg = self.identifier_placeholder
        return node


def safe_parse(source: str) -> Tuple[ast.AST | None, bool]:
    try:
        return ast.parse(source), True
    except SyntaxError:
        return None, False


def iter_imports(tree: ast.AST) -> Iterable[Tuple[str, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module, module.split(".")[0] if module else ""


def count_annotation_coverage(tree: ast.AST) -> Tuple[int, int]:
    annotated = 0
    total = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                annotated += 1
            total += 1
            for arg in list(node.args.args) + list(node.args.kwonlyargs):
                if arg.annotation is not None:
                    annotated += 1
                total += 1
            if node.args.vararg is not None:
                total += 1
                if node.args.vararg.annotation is not None:
                    annotated += 1
            if node.args.kwarg is not None:
                total += 1
                if node.args.kwarg.annotation is not None:
                    annotated += 1
    return annotated, total

