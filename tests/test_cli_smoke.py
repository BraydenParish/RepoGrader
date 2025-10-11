import json
from pathlib import Path

from cq.cli import main


def test_cli_smoke(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    (project_dir / "mod.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    exit_code = main(["scan", "--path", str(project_dir), "--format", "json", "--out", str(out_dir)])
    assert exit_code in (0, 2)
    data = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert "files" in data
    assert data["project"]["summary"]["grade"] >= 0

