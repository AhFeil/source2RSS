"""
对客户端测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s client/tests/test_client.py
"""
import pytest

from client.src.source2RSS_client import S2RProfile, Source2RSSClient
from configHandle import config

s2r_profile: S2RProfile = {
    "url": f"http://127.0.0.1:{config.port}",
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
