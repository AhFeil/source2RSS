"""
对 Web 接口 user 测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s tests/web/test_user.py
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


def test_index_of_user(setup_and_tear_down):
    response = client.get("/users/me/")
    assert response.status_code == 200

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
def test_register(setup_and_tear_down):
    data = {
        "invite_code": "source2RSS",
        "name": "pytest",
        "passwd": "zfZZFgf56zsd56"
    }
    header = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    response = client.post("/users/me/register", json=data, headers=header)
    assert response.status_code == 200
    response = client.post("/users/me/register", json=data, headers=header)
    assert response.status_code == 200 # todo 重复注册会失败
