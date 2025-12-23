# ruff: noqa: T201, SLF001
"""
对 config 测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s tests/test_config.py
"""
from collections import defaultdict

import pytest

from config_handle import config


@pytest.fixture
def setup_and_tear_down():
    print("This is run before each config test")
    yield
    print("This is run after each config test")

def is_result_consistent_simple(observed_counts: dict[str, int], expected_weights: list[tuple[str, int]], tolerance: float = 0.1) -> bool:
    """
    简单检查：判断实际比例是否在期望比例的容忍范围内

    Args:
        observed_counts: 观察到的计数
        expected_weights: 期望权重
        tolerance: 容忍度（如0.1表示±10%）
    """
    categories = [item[0] for item in expected_weights]
    weights = [item[1] for item in expected_weights]

    if set(observed_counts.keys()) != set(categories):
        return False

    total_observed = sum(observed_counts.values())
    total_weight = sum(weights)
    if total_observed == 0 or total_weight == 0:
        return False

    for i, category in enumerate(categories):
        actual_ratio = observed_counts[category] / total_observed
        expected_ratio = weights[i] / total_weight
        if abs(actual_ratio - expected_ratio) > tolerance:
            return False
    return True

def test_get_agent(setup_and_tear_down):
    cls_name = "CSLRXYZ"
    for _ in range(100):
        assert config.get_prefer_agent(cls_name) == "self"

def test_choose_agent(setup_and_tear_down):
    cls_name = "BilibiliUp"
    expected_weights = [('vfly2_direct_agent', 2), ('self', 1)]
    res = defaultdict(int)
    for _ in range(600):
        agent = config.get_prefer_agent(cls_name)
        res[agent] += 1
    assert is_result_consistent_simple(res, expected_weights, tolerance=0.05)
