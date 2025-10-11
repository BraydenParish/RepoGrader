import subprocess
from pathlib import Path
from unittest import mock

from cq.analyzers.lint import LintAnalyzer
from cq.analyzers.typing import TypingAnalyzer
from cq.config import Config


class DummyCompletedProcess:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_lint_analyzer_parses_messages(tmp_path: Path):
    cfg = Config.from_dict({})
    analyzer = LintAnalyzer(cfg)
    message = [{"path": str(tmp_path / "mod.py"), "symbol": "C0103"}]
    with mock.patch("subprocess.run", return_value=DummyCompletedProcess(stdout=json_dumps(message), returncode=2)):
        result = analyzer.analyze([str(tmp_path / "mod.py")])
    assert result.counts[str(tmp_path / "mod.py")]["C"] == 1
    assert result.weighted_scores[str(tmp_path / "mod.py")] < 100


def json_dumps(data):
    import json

    return json.dumps(data)


def test_typing_analyzer_parses_errors(tmp_path: Path):
    cfg = Config.from_dict({})
    analyzer = TypingAnalyzer(cfg)
    fake_output = f"{tmp_path / 'mod.py'}:1: error: Incompatible types\n"
    loc_map = {str(tmp_path / "mod.py"): 10}
    with mock.patch("subprocess.run", return_value=DummyCompletedProcess(stdout=fake_output, returncode=1)):
        result = analyzer.analyze([str(tmp_path / "mod.py")], loc_map, {str(tmp_path / "mod.py"): 0.0})
    assert result.errors[str(tmp_path / "mod.py")] == 1
    assert result.scores[str(tmp_path / "mod.py")] < 100

