"""
对客户端测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s client/tests/test_client.py
"""
from dataclasses import dataclass

import pytest

from source2RSS_client import S2RProfile, Source2RSSClient


@dataclass
class Config:
    url: str = "http://localhost:8536"
    query_username: str = "vfly2"
    query_password: str = "123456"

config = Config()


s2r_profile: S2RProfile = {
    "url": config.url,
    "username": config.query_username,
    "password": config.query_password,
    "source_name": "test_client_log",
}

@pytest.mark.asyncio
async def test_client():
    s2r_c = Source2RSSClient.create(s2r_profile)
    response = await s2r_c.post_article("test_client", "test_client summary")
    assert response
    assert response.status_code == 200

def test_client_send_test():
    _s2r_c = Source2RSSClient.create(s2r_profile, True)
