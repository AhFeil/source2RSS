"""对 Web 接口 query rss 测试"""
import asyncio
import base64

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from configHandle import config
from main import app

client = TestClient(app)


@pytest.fixture()
def setup_and_tear_down():
    print("This is run before each web test")
    yield
    print("This is run after each web test")


def get_headers(name, passwd):
    credentials = f"{name}:{passwd}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    headers = {
        "accept": "text/html",
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    return headers

def test_index_of_get(setup_and_tear_down):
    response = client.get("/query_rss/", headers=get_headers(config.query_username, config.query_password))
    assert response.status_code == 200


def test_query_rss_success(setup_and_tear_down):
    """测试触发更新的正常功能"""
    # 管理员访问
    response = client.get("/query_rss/YoutubeChannel/?q=bulianglin", headers=get_headers(config.query_username, config.query_password))
    assert response.status_code == 200
    # todo 普通用户访问

    # 未登录访问
    response = client.get("/query_rss/YoutubeChannel/?q=bulianglin")
    assert response.status_code == 401

    # todo 抓取器的 Access 是 user 级别，也要能访问


def test_query_rss_all_success(setup_and_tear_down):
    """全量测试触发更新"""
    # todo 从 usage 网页获得网址
    response = client.get("/query_rss/BentoMLBlog/", headers=get_headers(config.query_username, config.query_password))
    assert response.status_code == 200

    response = client.get("/query_rss/BilibiliUp/?q=483246073", headers=get_headers(config.query_username, config.query_password))
    assert response.status_code == 200

    response = client.get("/query_rss/MangaCopy/?q=花咲家的性福生活&q=huaxoajiedexinfushenghuo", headers=get_headers(config.query_username, config.query_password))
    assert response.status_code == 200

    response = client.get("/query_rss/YoutubeChannel/?q=bulianglin", headers=get_headers(config.query_username, config.query_password))
    assert response.status_code == 200


def test_query_rss_not_exist(setup_and_tear_down):
    """测试触发更新在抓取器不存在时表现"""
    response = client.get("/query_rss/NotExistScraper", headers=get_headers(config.query_username, config.query_password))
    assert response.status_code == 404
    response = client.get("/query_rss/Representative", headers=get_headers(config.query_username, config.query_password))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_query_rss_high_concurrency():
    """测试触发更新的并发表现"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_testserver") as ac: # type: ignore
        urls = [
            "/query_rss/BilibiliUp/?q=246370149",
            "/query_rss/BilibiliUp/?q=110529160",
            "/query_rss/BilibiliUp/?q=3225971",
            "/query_rss/BilibiliUp/?q=498040332",
            "/query_rss/BilibiliUp/?q=121752611",
            "/query_rss/BilibiliUp/?q=471703759",
            "/query_rss/BilibiliUp/?q=367413928",
            "/query_rss/BilibiliUp/?q=669171629",
            "/query_rss/BilibiliUp/?q=72270557",
            "/query_rss/BilibiliUp/?q=178429408",
            "/query_rss/BilibiliUp/?q=246370149",
            "/query_rss/BilibiliUp/?q=110529160",
            "/query_rss/BilibiliUp/?q=3225971",
            "/query_rss/BilibiliUp/?q=498040332",
            "/query_rss/BilibiliUp/?q=121752611",
            "/query_rss/BilibiliUp/?q=471703759",
            "/query_rss/BilibiliUp/?q=3076225",
            "/query_rss/BilibiliUp/?q=40545158",
            "/query_rss/BilibiliUp/?q=3546567556466963",
            "/query_rss/BilibiliUp/?q=330415548",
            "/query_rss/BilibiliUp/?q=386852445",
            "/query_rss/BilibiliUp/?q=3493117728656046",
            "/query_rss/BilibiliUp/?q=1659399",
            "/query_rss/YoutubeChannel/?q=bulianglin"
        ]
        headers = get_headers(config.query_username, config.query_password)

        tasks = (ac.get(url, headers=headers) for url in urls)
        responses = await asyncio.gather(*tasks)

        for response in responses:
            assert response.status_code == 200
