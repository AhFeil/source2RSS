"""
对 Web 接口 get rss 测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s tests/web/test_usage.py
"""
import pytest
from fastapi.testclient import TestClient

from main import fast_app

client = TestClient(fast_app)


@pytest.fixture()
def setup_and_tear_down():
    print("This is run before each web test")
    yield
    print("This is run after each web test")


def test_index_of_usage(setup_and_tear_down):
    response = client.get("/usage/")
    assert response.status_code == 200


def test_scraper_usage(setup_and_tear_down):
    # todo 应该遍历网页中所有网址测试
    response = client.get("/usage/Chiphell/")
    assert response.status_code == 200
