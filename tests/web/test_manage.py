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
from tests.web.test_query_rss import get_headers

client = TestClient(fast_app)


def get_headers_j(name, passwd):
    credentials = f"{name}:{passwd}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    return headers


@pytest.fixture
def setup_and_tear_down():
    print("This is run before each web test")
    yield
    print("This is run after each web test")


def test_index_of_manage(setup_and_tear_down):
    response = client.get("/manage/", headers=get_headers(config.query_username, config.query_password))
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
def test_update_invite_code(setup_and_tear_down):
    data = {
        "code": "source2RSS",
        "count": 1
    }
    response = client.post("/manage/invite_code", json=data, headers=get_headers_j(config.query_username, config.query_password))
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
    # response = client.post("/manage/crawler/run_all", json={}, headers=get_headers_j(config.query_username, config.query_password))
    # assert response.status_code == 200

    response = client.post("/manage/crawler/run_all", json={})
    assert response.status_code == 401

"""
更新抓取器配置

todo 更新后，应该在网页上能找到相应的改变
"""
