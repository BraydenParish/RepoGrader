import ast
import io
import json
import shutil
import statistics
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from git import Repo
from git.exc import GitCommandError
from pylint.lint import Run as PylintRun

try:  # Pylint <= 2.17
    from pylint.reporters.collecting import CollectingReporter
except ModuleNotFoundError:  # Pylint >= 3.0
    from pylint.reporters.collecting_reporter import CollectingReporter
from radon.complexity import cc_visit
from radon.metrics import mi_visit
import tokenize


APP_TITLE = "RepoGrader Pro (Lite)"
CLONE_TARGET = Path("/tmp/repo")
SKIP_DIRS = {"venv", "__pycache__", "tests", "node_modules", ".git"}

app = FastAPI(title=APP_TITLE)
templates = Jinja2Templates(directory="templates")


def clean_clone_dir(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.parent.mkdir(parents=True, exist_ok=True)


def clone_repository(repo_url: str, target: Path) -> Path:
    clean_clone_dir(target)
    try:
        Repo.clone_from(repo_url, target)
    except GitCommandError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to clone repository: {exc}") from exc
    return target


def read_code(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback if a file has a different encoding.
        return path.read_text(encoding="latin-1", errors="ignore")


def compute_comment_density(source: str) -> Tuple[int, float]:
    total_lines = len(source.splitlines())
    comment_lines = 0
    if not source.strip():
        return 0, 0.0

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        tokens = []

    seen_comment_lines = set()
    for token in tokens:
        if token.type == tokenize.COMMENT:
            seen_comment_lines.add(token.start[0])
    comment_lines = len(seen_comment_lines)

    density = comment_lines / total_lines if total_lines else 0.0
    return total_lines, density


def compute_type_hint_coverage(tree: ast.AST) -> Tuple[int, float]:
    total_functions = 0
    annotated_functions = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total_functions += 1
            all_args_annotated = True

            args = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
            if node.args.vararg:
                args.append(node.args.vararg)
            if node.args.kwarg:
                args.append(node.args.kwarg)

            for arg in args:
                if getattr(arg, "annotation", None) is None:
                    all_args_annotated = False
                    break

            return_annotated = node.returns is not None
            if all_args_annotated and return_annotated:
                annotated_functions += 1

    coverage = annotated_functions / total_functions if total_functions else 0.0
    return total_functions, coverage


def compute_avg_function_length(tree: ast.AST) -> Tuple[int, float]:
    lengths: List[int] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is not None:
                lengths.append(end_lineno - node.lineno + 1)
            else:
                lengths.append(len(node.body))
    count = len(lengths)
    avg_length = statistics.mean(lengths) if lengths else 0.0
    return count, avg_length


def run_pylint(file_path: Path) -> int:
    reporter = CollectingReporter()
    try:
        PylintRun(
            [str(file_path), "--score=n", "--exit-zero"],
            reporter=reporter,
            do_exit=False,
        )
    except Exception:
        return len(reporter.messages)
    return len(reporter.messages)


def analyze_file(path: Path) -> Dict[str, Any]:
    source = read_code(path)
    metrics: Dict[str, Any] = {}

    if not source.strip():
        metrics.update(
            {
                "cyclomatic_complexity": 0.0,
                "maintainability_index": 100.0,
                "lint_warnings": 0,
                "lint_warnings_per_100_loc": 0.0,
                "comment_density": 0.0,
                "function_count": 0,
                "avg_function_length": 0.0,
                "type_hint_coverage": 0.0,
                "loc": 0,
            }
        )
        return metrics

    # Cyclomatic complexity via radon (average per block)
    try:
        cc_results = cc_visit(source)
        complexities = [block.complexity for block in cc_results]
        avg_complexity = statistics.mean(complexities) if complexities else 0.0
    except Exception:
        avg_complexity = 0.0

    # Maintainability index
    try:
        maintainability = mi_visit(source, True)
    except Exception:
        maintainability = 50.0

    # Comment density
    loc, comment_density = compute_comment_density(source)

    # AST-based metrics
    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = ast.parse("pass")

    function_count, avg_function_length = compute_avg_function_length(tree)
    total_functions, type_hint_coverage = compute_type_hint_coverage(tree)

    # Lint warnings
    lint_warnings = run_pylint(path)
    normalized_loc = max(loc, 1)
    lint_per_100 = (lint_warnings / normalized_loc) * 100

    metrics.update(
        {
            "cyclomatic_complexity": avg_complexity,
            "maintainability_index": maintainability,
            "lint_warnings": lint_warnings,
            "lint_warnings_per_100_loc": lint_per_100,
            "comment_density": comment_density,
            "type_hint_coverage": type_hint_coverage,
            "function_count": function_count,
            "avg_function_length": avg_function_length,
            "loc": loc,
            "total_functions": total_functions,
        }
    )
    return metrics


def map_metric(value: float, thresholds: List[Tuple[float, int]], reverse: bool = False) -> int:
    """
    thresholds: list of tuples (limit, score) sorted ascending if not reverse else descending.
    reverse=False means value < limit -> score.
    reverse=True means value > limit -> score.
    """
    if reverse:
        for limit, score in thresholds:
            if value > limit:
                return score
        return thresholds[-1][1] if thresholds else 0
    for limit, score in thresholds:
        if value < limit:
            return score
    return thresholds[-1][1] if thresholds else 0


def score_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    complexity_score = map_metric(
        metrics["cyclomatic_complexity"],
        [(10, 100), (20, 70), (float("inf"), 40)],
    )

    maintainability = metrics["maintainability_index"]
    if maintainability > 85:
        maintainability_score = 100
    elif maintainability > 70:
        maintainability_score = 80
    elif maintainability > 50:
        maintainability_score = 60
    else:
        maintainability_score = 40

    lint_score = 100
    lint_metric = metrics["lint_warnings_per_100_loc"]
    if lint_metric == 0:
        lint_score = 100
    elif lint_metric <= 5:
        lint_score = 80
    elif lint_metric <= 10:
        lint_score = 60
    else:
        lint_score = 40

    comment_density = metrics["comment_density"]
    if comment_density >= 0.1:
        comment_score = 100
    elif comment_density >= 0.05:
        comment_score = 80
    elif comment_density >= 0.02:
        comment_score = 60
    else:
        comment_score = 40

    type_hint_cov = metrics["type_hint_coverage"]
    if type_hint_cov >= 0.8:
        hint_score = 100
    elif type_hint_cov >= 0.5:
        hint_score = 80
    elif type_hint_cov >= 0.2:
        hint_score = 60
    else:
        hint_score = 40

    avg_func_len = metrics["avg_function_length"]
    if avg_func_len < 30:
        func_len_score = 100
    elif avg_func_len <= 60:
        func_len_score = 80
    else:
        func_len_score = 50

    final_score = round(
        0.25 * maintainability_score
        + 0.2 * complexity_score
        + 0.2 * lint_score
        + 0.1 * comment_score
        + 0.1 * hint_score
        + 0.15 * func_len_score
    )

    if final_score >= 90:
        letter = "A"
    elif final_score >= 80:
        letter = "B"
    elif final_score >= 70:
        letter = "C"
    elif final_score >= 60:
        letter = "D"
    else:
        letter = "F"

    reasons: List[str] = []
    if maintainability_score < 80:
        reasons.append(f"Maintainability index {maintainability:.1f}")
    if complexity_score < 80:
        reasons.append(f"Average complexity {metrics['cyclomatic_complexity']:.1f}")
    if lint_score < 80:
        reasons.append(
            f"{metrics['lint_warnings']} lint warnings (~{metrics['lint_warnings_per_100_loc']:.1f}/100 LOC)"
        )
    if comment_score < 80:
        reasons.append(f"Low comment density ({comment_density:.2f})")
    if hint_score < 80 and metrics["total_functions"]:
        reasons.append(f"Type hints on {type_hint_cov*100:.0f}% of functions")
    if func_len_score < 80 and metrics["function_count"]:
        reasons.append(f"Average function length {avg_func_len:.1f} LOC")

    if not reasons:
        reasons.append("Balanced metrics across complexity, lint, and documentation")

    return {
        "numeric_score": final_score,
        "letter_grade": letter,
        "reasons": "; ".join(reasons[:3]),
        "components": {
            "maintainability": maintainability_score,
            "complexity": complexity_score,
            "lint": lint_score,
            "comment_density": comment_score,
            "type_hints": hint_score,
            "function_length": func_len_score,
        },
    }


def run_pip_audit(requirements_path: Path) -> Optional[Dict[str, Any]]:
    try:
        completed = subprocess.run(
            ["pip-audit", "-r", str(requirements_path), "--format", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None

    if completed.returncode not in (0, 1):
        return None

    try:
        payload = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return None

    vulnerability_count = 0
    for item in payload:
        vulnerabilities = item.get("vulns") or []
        vulnerability_count += len(vulnerabilities)

    if vulnerability_count == 0:
        vuln_score = 100
    elif vulnerability_count <= 2:
        vuln_score = 70
    else:
        vuln_score = 40

    return {
        "count": vulnerability_count,
        "score": vuln_score,
        "raw": payload,
    }


def grade_repo(repo_url: str) -> Dict[str, Any]:
    repo_url = repo_url.strip()
    if not repo_url:
        raise HTTPException(status_code=400, detail="Repository URL is required.")

    repo_path = clone_repository(repo_url, CLONE_TARGET)
    results: Dict[str, Any] = {"files": {}}
    numeric_scores: List[int] = []

    for path in repo_path.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        metrics = analyze_file(path)
        scored = score_metrics(metrics)
        relative_path = str(path.relative_to(repo_path))
        results["files"][relative_path] = {
            "grade": scored["letter_grade"],
            "score": scored["numeric_score"],
            "reason": scored["reasons"],
            "metrics": metrics,
        }
        numeric_scores.append(scored["numeric_score"])

    if not results["files"]:
        raise HTTPException(status_code=404, detail="No Python files found in the repository.")

    repo_score = round(statistics.mean(numeric_scores))
    if repo_score >= 90:
        repo_grade = "A"
    elif repo_score >= 80:
        repo_grade = "B"
    elif repo_score >= 70:
        repo_grade = "C"
    elif repo_score >= 60:
        repo_grade = "D"
    else:
        repo_grade = "F"

    results.update(
        {
            "repo_url": repo_url,
            "repo_score": repo_score,
            "repo_grade": repo_grade,
        }
    )

    requirements_path = repo_path / "requirements.txt"
    if requirements_path.exists():
        vuln_info = run_pip_audit(requirements_path)
        if vuln_info:
            results["vulnerabilities"] = vuln_info

    return results


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "results": None,
        },
    )


@app.post("/analyze", response_class=HTMLResponse)
async def analyze_repo(request: Request, repo_url: str = Form(...)) -> HTMLResponse:
    analysis = await run_in_threadpool(grade_repo, repo_url)
    app.state.last_result = analysis
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "results": analysis,
        },
    )


@app.get("/api/results")
async def api_results() -> Dict[str, Any]:
    result = getattr(app.state, "last_result", None)
    if not result:
        raise HTTPException(status_code=404, detail="No analysis has been run yet.")
    return result


if __name__ == "__main__":
    print("Run the app with: uvicorn main:app --reload")
