"""Configuration loading for Code Quotient."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional

try:  # pragma: no cover - optional dependency
    import yaml
except ImportError:  # pragma: no cover - fallback
    yaml = None
import json


DEFAULT_CONFIG = {
    "paths": {
        "include": ["./"],
        "exclude": ["/.venv/", "/venv/", "/build/", "/dist/", "/site-packages/"],
    },
    "arch": {
        "layers": ["core", "api", "ui"],
        "map": {"src/core": "core", "src/api": "api", "src/ui": "ui"},
        "allowed_edges": [
            ["core", "core"],
            ["api", "core"],
            ["api", "api"],
            ["ui", "api"],
            ["ui", "core"],
            ["ui", "ui"],
        ],
    },
    "weights": {
        "metrics": {
            "duplication": 0.25,
            "lint": 0.30,
            "typing": 0.20,
            "complexity": 0.25,
        },
        "pylint_categories": {"C": 0.25, "W": 0.5, "R": 0.4, "E": 1.0},
        "roles": {
            "default": 1.0,
            "test": 0.35,
            "config": 0.35,
            "vendor": 0.2,
            "generated": 0.0,
        },
    },
    "tools": {
        "pylint_cmd": "pylint",
        "mypy_cmd": "mypy",
        "timeouts": {"pylint": 90, "mypy": 120},
    },
    "duplication": {
        "k": 25,
        "w": 4,
        "normalize": {
            "strip_literals": True,
            "strip_comments": True,
            "identifier_placeholder": "ID",
        },
    },
    "bootstrap": {"iterations": 100, "seed": 1337},
    "scoring": {
        "complexity_scale": {"target_per_loc": 0.25, "hard_cap": 50},
        "typing_error_scale": {"per_1k_loc": {"max_score_at_0": 100, "zero_score_at_20": 0}},
    },
    "report": {"format": ["json", "md"], "out_dir": ".cq-out"},
}


@dataclass
class PathsConfig:
    include: List[str]
    exclude: List[str]


@dataclass
class ArchConfig:
    layers: List[str]
    mapping: Dict[str, str]
    allowed_edges: List[List[str]]


@dataclass
class ToolsConfig:
    pylint_cmd: str
    mypy_cmd: str
    timeouts: Dict[str, int]


@dataclass
class DuplicationConfig:
    k: int
    w: int
    normalize: Dict[str, object]


@dataclass
class BootstrapConfig:
    iterations: int
    seed: int


@dataclass
class ComplexityScale:
    target_per_loc: float
    hard_cap: int


@dataclass
class TypingScale:
    max_score_at_0: float
    zero_score_at_20: float


@dataclass
class ScoringConfig:
    complexity_scale: ComplexityScale
    typing_error_scale: TypingScale


@dataclass
class ReportConfig:
    format: List[str]
    out_dir: str


@dataclass
class Config:
    paths: PathsConfig
    arch: ArchConfig
    weights: Dict[str, Dict[str, float]]
    tools: ToolsConfig
    duplication: DuplicationConfig
    bootstrap: BootstrapConfig
    scoring: ScoringConfig
    report: ReportConfig

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Config":
        merged = _deep_merge(DEFAULT_CONFIG, data)
        paths = merged["paths"]
        arch = merged["arch"]
        weights = merged["weights"]
        tools = merged["tools"]
        duplication = merged["duplication"]
        bootstrap = merged["bootstrap"]
        scoring = merged["scoring"]
        report = merged["report"]
        return cls(
            paths=PathsConfig(list(paths["include"]), list(paths["exclude"])),
            arch=ArchConfig(list(arch["layers"]), dict(arch["map"]), list(arch["allowed_edges"])),
            weights={k: dict(v) for k, v in weights.items()},
            tools=ToolsConfig(
                pylint_cmd=str(tools["pylint_cmd"]),
                mypy_cmd=str(tools["mypy_cmd"]),
                timeouts={k: int(v) for k, v in tools["timeouts"].items()},
            ),
            duplication=DuplicationConfig(
                k=int(duplication["k"]),
                w=int(duplication["w"]),
                normalize=dict(duplication["normalize"]),
            ),
            bootstrap=BootstrapConfig(
                iterations=int(bootstrap["iterations"]),
                seed=int(bootstrap["seed"]),
            ),
            scoring=ScoringConfig(
                complexity_scale=ComplexityScale(
                    target_per_loc=float(scoring["complexity_scale"]["target_per_loc"]),
                    hard_cap=int(scoring["complexity_scale"]["hard_cap"]),
                ),
                typing_error_scale=TypingScale(
                    max_score_at_0=float(
                        scoring["typing_error_scale"]["per_1k_loc"]["max_score_at_0"]
                    ),
                    zero_score_at_20=float(
                        scoring["typing_error_scale"]["per_1k_loc"]["zero_score_at_20"]
                    ),
                ),
            ),
            report=ReportConfig(format=list(report["format"]), out_dir=str(report["out_dir"])),
        )

    @classmethod
    def load(cls, path: Optional[Path]) -> "Config":
        if path is None:
            return cls.from_dict({})
        text = Path(path).read_text()
        data = _safe_yaml_load(text)
        return cls.from_dict(data)


def _deep_merge(base: Mapping[str, object], override: Mapping[str, object]) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for key, value in base.items():
        result[key] = value
    for key, value in override.items():
        if key in result and isinstance(result[key], Mapping) and isinstance(value, Mapping):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def dump_default_yaml() -> str:
    """Return a YAML string (or JSON fallback) for the default configuration."""
    if yaml is None:
        return json.dumps(DEFAULT_CONFIG, indent=2)
    return yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False)


def _safe_yaml_load(text: str) -> Dict[str, object]:
    if not text.strip():
        return {}
    if yaml is not None:
        loaded = yaml.safe_load(text)
        return loaded or {}
    return json.loads(text)

