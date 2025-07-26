"""
对 Web 接口 post rss 测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s tests/web/test_post_rss.py
"""
import base64
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from configHandle import config
from main import app

client = TestClient(app)


@pytest.fixture()
def setup_and_tear_down():
    print("This is run before each web test")
    yield
    print("This is run after each web test")


def test_delivery(setup_and_tear_down):
    credentials = f"{config.query_username}:{config.query_password}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    data_raw = [{
            "title": "title",
            "link": "http://rss.vfly2.com/query_rss/pytest_delivery.xml/#" + str(datetime.now().timestamp()),
            "summary": "summary",
            "content": "summary",
            "pub_time": datetime.now().strftime("%Y-%m-%d")
        }]

    response = client.post("/post_src/pytest_delivery/", headers=headers, json=data_raw)
    assert response.status_code == 200
