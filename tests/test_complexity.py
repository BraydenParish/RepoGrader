from cq.analyzers.complexity import ComplexityAnalyzer
from cq.config import Config


def test_complexity_increases_with_branches():
    cfg = Config.from_dict({})
    analyzer = ComplexityAnalyzer(cfg)
    sources = {
        "simple.py": "def f():\n    return 1\n",
        "complex.py": "def f(x):\n    if x:\n        return 1\n    else:\n        return 2\n",
    }
    loc = {"simple.py": 2, "complex.py": 5}
    result = analyzer.analyze(sources, loc)
    assert result.raw["complex.py"] > result.raw["simple.py"]
    assert result.scores["complex.py"] <= result.scores["simple.py"]

