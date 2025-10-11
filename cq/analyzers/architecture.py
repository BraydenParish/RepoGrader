"""Architecture conformance analysis."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from ..config import ArchConfig
from ..utils.ast_tools import iter_imports, safe_parse


@dataclass
class ArchitectureViolation:
    file: str
    from_layer: str
    to_layer: str
    import_name: str


class ArchitectureAnalyzer:
    def __init__(self, config: ArchConfig) -> None:
        self.config = config
        self.sorted_prefixes = sorted(config.mapping.items(), key=lambda kv: len(kv[0]), reverse=True)

    def analyze(self, files: Dict[str, str]) -> List[ArchitectureViolation]:
        violations: List[ArchitectureViolation] = []
        for path, source in files.items():
            tree, success = safe_parse(source)
            if not success or tree is None:
                continue
            from_layer = self._layer_for_path(path)
            if from_layer is None:
                continue
            for full_name, root in iter_imports(tree):
                target_layer = self._layer_for_module(full_name or root)
                if target_layer is None:
                    continue
                if [from_layer, target_layer] not in self.config.allowed_edges:
                    violations.append(
                        ArchitectureViolation(
                            file=path,
                            from_layer=from_layer,
                            to_layer=target_layer,
                            import_name=full_name,
                        )
                    )
        return violations

    def _layer_for_path(self, path: str) -> str | None:
        normalized = path.replace("\\", "/")
        for prefix, layer in self.sorted_prefixes:
            if normalized.startswith(prefix):
                return layer
        return None

    def _layer_for_module(self, module: str) -> str | None:
        normalized = module.replace(".", "/")
        for prefix, layer in self.sorted_prefixes:
            if normalized.startswith(prefix):
                return layer
        return None

