"""Filesystem helpers for cq."""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple

ROLE_HINTS = {
    "test": ["tests", "test_"],
    "config": ["config", "settings", "cfg", "ini", "yml", "yaml"],
    "vendor": ["vendor", "third_party", "site-packages"],
    "generated": ["build", "dist"],
}


def iter_python_files(include: Iterable[str], exclude: Iterable[str]) -> Iterator[Path]:
    includes = [Path(p).resolve() for p in include]
    excludes = [Path(p).resolve() for p in exclude]
    seen = set()
    for base in includes:
        base_path = base if base.is_absolute() else Path.cwd() / base
        if not base_path.exists():
            continue
        for path in base_path.rglob("*.py"):
            abs_path = path.resolve()
            if _is_excluded(abs_path, excludes):
                continue
            if abs_path in seen:
                continue
            seen.add(abs_path)
            yield abs_path


def _is_excluded(path: Path, excludes: List[Path]) -> bool:
    for pat in excludes:
        if str(path).startswith(str(pat)):
            return True
    return False


def detect_role(path: Path) -> str:
    lower = str(path).lower()
    for role, hints in ROLE_HINTS.items():
        for hint in hints:
            if hint in lower:
                return role
    return "default"


def read_text(path: Path) -> Tuple[str, int]:
    text = path.read_text(encoding="utf-8")
    loc = sum(1 for _ in text.splitlines())
    return text, loc

