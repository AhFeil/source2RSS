"""
对客户端测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s client/tests/test_client.py
"""
import pytest

from client.src.source2RSS_client import S2RProfile, Source2RSSClient
from configHandle import config

s2r_profile: S2RProfile = {
    "ip_or_domain": "127.0.0.1",
    "port": config.port,
    "username": config.query_username,
    "password": config.query_password,
    "source_name": "test_client_log",
}

@pytest.mark.skip(reason="需要启动服务端")
@pytest.mark.asyncio
async def test_client():
    s2r_c = Source2RSSClient.create(s2r_profile)
    response = await s2r_c.post_article("test_client", "test_client summary")
    assert response and response.status_code == 200

@pytest.mark.skip(reason="需要启动服务端")
def test_client_send_test():
    _s2r_c = Source2RSSClient.create(s2r_profile, True)
