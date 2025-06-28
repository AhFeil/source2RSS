"""对 Web 接口 get rss 测试"""
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


def test_index_of_get(setup_and_tear_down):
    response = client.get("/source2rss")
    assert response.status_code == 200


def test_get_saved_rss(setup_and_tear_down):
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
def test_get_user_rss(setup_and_tear_down):
    # 访问的网址不符合格式
    response = client.get(f"/source2rss/{config.query_username}/我靠焚尸超凡入圣/")
    assert response.status_code == 400
    response = client.get(f"/source2rss/{config.query_username}/.xml/")
    assert response.status_code == 404

    # 管理员可以访问任何一个
    response = client.get(f"/source2rss/{config.query_username}/我靠焚尸超凡入圣.xml/")
    assert response.status_code == 200
    response = client.get(f"/source2rss/{config.query_username}/我靠焚尸超凡入圣.json/")
    assert response.status_code == 200
    response = client.get(f"/source2rss/{config.query_username}/不存在的源.json/")
    assert response.status_code == 404
    # 普通用户可以访问其下名单里的
    response = client.get("/source2rss/yyy/我靠焚尸超凡入圣.xml/")
    assert response.status_code == 200
    response = client.get("/source2rss/yyy/我靠焚尸超凡入圣.json/")
    assert response.status_code == 200

    # 用户不存在
    response = client.get("/source2rss/invalid_user/我靠焚尸超凡入圣.xml/")
    assert response.status_code == 404
    response = client.get("/source2rss/invalid_user/我靠焚尸超凡入圣.json/")
    assert response.status_code == 404
    # todo 用户存在但请求的源不再其允许查看的名单中
