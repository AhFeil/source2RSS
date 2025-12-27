# ruff: noqa: T201
"""
对 Web 接口 user 测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s tests/web/test_user.py
"""
import pytest
from fastapi.testclient import TestClient

from config_handle import config
from main import fast_app
from tests.web.utility import get_headers

client = TestClient(fast_app)


@pytest.fixture
def setup_and_tear_down():
    print("This is run before each web test")
    yield
    print("This is run after each web test")


def test_index_of_user(setup_and_tear_down):
    response = client.get("/users/me/")
    assert response.status_code == 401

"""
curl -X 'POST' \
  'http://rss.vfly2.com/users/me/register' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "invite_code": "source2RSS",
  "name": "pytest",
  "passwd": "zfZZFgf56zsd56"
}'
"""
def register_user(data: dict, test_client: TestClient):
    header = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    return test_client.post("/users/me/register", json=data, headers=header)


def test_register(setup_and_tear_down):
    data = {
        "invite_code": "source2RSS",
        "name": "pytest",
        "passwd": "zfZZFgf56zsd56"
    }
    response = register_user(data, client)
    assert response.status_code == 200
    response = register_user(data, client)
    assert response.status_code == 200 # todo 重复注册会失败


def add_source_to_user(user_name: str, source_name: str, test_client: TestClient):
    data = {"source_name": source_name}
    return test_client.post(f"/users/{user_name}/user_sources", json=data, headers=get_headers(config.query_username, config.query_password))


def test_add_source(setup_and_tear_down):
    response = add_source_to_user("pytest", "Old Stone", client)
    assert response.status_code == 200 # TODO 校验 msg
    response = add_source_to_user("pytest", "Old%20Stone", client)
    assert response.status_code == 200
