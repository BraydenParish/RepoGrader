from cq.analyzers.duplication import DuplicationAnalyzer
from cq.config import Config


def test_duplication_detects_overlap():
    cfg = Config.from_dict({})
    analyzer = DuplicationAnalyzer(cfg.duplication)
    sources = {
        "a.py": "def add(x, y):\n    return x + y\n",
        "b.py": "def add_numbers(a, b):\n    return a + b\n",
    }
    result = analyzer.analyze(sources)
    assert result.ratios["a.py"] > 0
    assert result.ratios["b.py"] > 0


def test_duplication_handles_unique():
    cfg = Config.from_dict({})
    analyzer = DuplicationAnalyzer(cfg.duplication)
    sources = {
        "a.py": "def add(x, y):\n    return x + y\n",
        "b.py": "def mul(a, b):\n    return a * b\n",
    }
    result = analyzer.analyze(sources)
    assert result.ratios["a.py"] == 0
    assert result.ratios["b.py"] == 0

