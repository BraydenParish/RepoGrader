from cq.analyzers.architecture import ArchitectureAnalyzer
from cq.config import Config


def test_architecture_violation_detected():
    cfg = Config.from_dict({
        "arch": {
            "map": {"src/core": "core", "src/ui": "ui"},
            "allowed_edges": [["core", "core"], ["ui", "ui"]],
        }
    })
    analyzer = ArchitectureAnalyzer(cfg.arch)
    files = {
        "src/ui/view.py": "import src.core.service\n",
        "src/core/service.py": "def go():\n    pass\n",
    }
    violations = analyzer.analyze(files)
    assert len(violations) == 1
    assert violations[0].from_layer == "ui"
    assert violations[0].to_layer == "core"


def test_architecture_allows_valid_edges():
    cfg = Config.from_dict({
        "arch": {
            "map": {"src/core": "core", "src/api": "api"},
            "allowed_edges": [["api", "core"], ["core", "core"]],
        }
    })
    analyzer = ArchitectureAnalyzer(cfg.arch)
    files = {
        "src/api/handler.py": "import src.core.service\n",
    }
    violations = analyzer.analyze(files)
    assert violations == []

