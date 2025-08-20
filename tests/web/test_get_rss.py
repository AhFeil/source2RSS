"""
对 Web 接口 get rss 测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s tests/web/test_get_rss.py
"""
import pytest
from fastapi.testclient import TestClient

from configHandle import config
from main import fast_app

client = TestClient(fast_app)


@pytest.fixture()
def setup_and_tear_down():
    print("This is run before each web test")
    yield
    print("This is run after each web test")


def test_index_of_get(setup_and_tear_down):
    response = client.get("/source2rss")
    assert response.status_code == 200


def test_get_public_rss(setup_and_tear_down):
    # 访问的网址不符合格式
    response = client.get("/source2rss/BentoML Blog/")
    assert response.status_code == 400
    response = client.get("/source2rss/.xml/")
    assert response.status_code == 404

    # 访问有且缓存了的
    response = client.get("/source2rss/BentoML Blog.xml/")
    assert response.status_code == 200
    response = client.get("/source2rss/BentoML Blog.json/")
    assert response.status_code == 200

    # todo 访问有但没缓存的

    # 访问没有的
    response = client.get("/source2rss/edfghjkl.xml/")
    assert response.status_code == 404
    response = client.get("/source2rss/edfghjkl.json/")
    assert response.status_code == 404
    response = client.get("/source2rss/BentoML Blog.bash/")
    assert response.status_code == 404


# todo 自动创建普通用户
# todo 测试前先主动请求一次，保证已有
def test_get_their_rss(setup_and_tear_down):
    # 访问的网址不符合格式
    response = client.get(f"/source2rss/{config.query_username}/fanqie_book_6999592647790693413/")
    assert response.status_code == 400
    response = client.get(f"/source2rss/{config.query_username}/.xml/")
    assert response.status_code == 404
    response = client.get(f"/source2rss/{config.query_username}/我靠焚尸超凡入圣/")
    assert response.status_code == 400

    # 管理员可以访问任何一个
    response = client.get(f"/source2rss/{config.query_username}/fanqie_book_6999592647790693413.xml/")
    assert response.status_code == 200
    response = client.get(f"/source2rss/{config.query_username}/fanqie_book_6999592647790693413.json/")
    assert response.status_code == 200
    response = client.get(f"/source2rss/{config.query_username}/不存在的源.json/")
    assert response.status_code == 404
    # todo 普通用户可以访问其下名单里的
    response = client.get("/source2rss/test_1/fanqie_book_6999592647790693413.xml/")
    assert response.status_code == 200
    response = client.get("/source2rss/test_1/fanqie_book_6999592647790693413.json/")
    assert response.status_code == 200

    # 用户不存在
    response = client.get("/source2rss/invalid_user/fanqie_book_6999592647790693413.xml/")
    assert response.status_code == 404
    response = client.get("/source2rss/invalid_user/fanqie_book_6999592647790693413.json/")
    assert response.status_code == 404
    # todo 用户存在但请求的源不再其允许查看的名单中
