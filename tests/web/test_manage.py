# ruff: noqa: E501, T201
"""
对 Web 接口 manage 测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s tests/web/test_manage.py
"""
import base64

import pytest
from fastapi.testclient import TestClient

from configHandle import config
from main import fast_app
from tests.web.utility import get_headers

client = TestClient(fast_app)


@pytest.fixture
def setup_and_tear_down():
    print("This is run before each web test")
    yield
    print("This is run after each web test")


def test_index_of_manage(setup_and_tear_down):
    response = client.get("/manage/", headers=get_headers(config.query_username, config.query_password, accept="html"))
    assert response.status_code == 200

    response = client.get("/manage/")
    assert response.status_code == 401


"""
更新邀请码

curl -X 'POST' \
  'http://rss.vfly2.com/manage/invite_code' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Basic $(echo -n 'vfly2:123456' | base64 | tr -d '\n')" \
  -d '{"code": "source2RSS", "count": 1}'
"""
def update_invite_code(code: str, count: int, test_client):
    data = {"code": code, "count": count}
    return test_client.post("/manage/invite_code", json=data, headers=get_headers(config.query_username, config.query_password))

def test_update_invite_code(setup_and_tear_down):
    response = update_invite_code("source2RSS", 1, client)
    assert response.status_code == 200

"""
抓取器全跑一遍

curl -X 'POST' \
  'http://rss.vfly2.com/manage/crawler/run_all' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Basic $(echo -n 'vfly2:123456' | base64 | tr -d '\n')" \
  -d '{}'
"""
def test_run_all_crawler(setup_and_tear_down):
    # todo
    # response = client.post("/manage/crawler/run_all", json={}, headers=get_headers(config.query_username, config.query_password))
    # assert response.status_code == 200

    response = client.post("/manage/crawler/run_all", json={})
    assert response.status_code == 401

"""
更新抓取器配置

todo 更新后，应该在网页上能找到相应的改变
"""
