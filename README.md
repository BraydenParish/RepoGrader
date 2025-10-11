# Code Quotient (cq)

Code Quotient (cq) is a deterministic Python 3.11 code quality analyzer that focuses on "Phase 1 — Deterministic Enhancements". It inspects a repository and produces a weighted quality report across duplication, architecture conformance, lint quality, static typing, and cognitive complexity. Reports are emitted in both JSON (schema validated) and Markdown formats.

## Features

- Winnowing-based duplication analysis with AST normalization for Python sources
- Reflexion-style architecture conformance against configurable layers
- Aggregated lint (pylint) and typing (mypy) metrics with graceful degradation when tools are unavailable
- Sonar-inspired cognitive complexity scoring
- Confidence estimation with bootstrap confidence intervals
- Deterministic output ordering and stable hashing

## Installation

```bash
pip install .
```

## Usage

```bash
cq scan --path . --format both
```

Outputs are written under `.cq-out/` by default.

For configuration, copy `sample/cq.yml` and adjust paths, weights, or tool commands as needed.

## Development

Run the automated checks with:

```bash
pytest -q
```

