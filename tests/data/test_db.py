"""
对数据库操作测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s tests/data/test_db.py
"""
from datetime import datetime

import pytest

from src.data.sqlite_intf import DatabaseIntf, SQliteConnInfo, SQliteIntf
from src.scraper import AccessLevel, ArticleDict, SortKey, SrcMetaDict


@pytest.fixture()
def setup_and_tear_down():
    print("This is run before each db test")
    yield
    print("This is run after each db test")

def test_sqlite(setup_and_tear_down):
    info = SQliteConnInfo("sqlite:///tests/config_and_data_files/test.db")
    db_intf: DatabaseIntf = SQliteIntf.connect(info)

    db_intf._clear_db()
    source_info: SrcMetaDict = {
        'name': 'BentoML Blog',
        'link': 'https://www.bentoml.com/blog',
        'desc': "description---------",
        'lang': "En",
        'tags': "",
        'key4sort': SortKey.PUB_TIME,
        "access": AccessLevel.USER,
        "table_name": "BentoML Blog",
    }
    db_intf.exist_source_meta(source_info)
    assert db_intf.get_source_info(source_info["name"]) == source_info
    source_info["desc"] = "szdbdxgnxmhxfm"
    db_intf.exist_source_meta(source_info)
    assert db_intf.get_source_info(source_info["name"]) == source_info

    article: ArticleDict = {
        "id": 33,
        "title": "res.title",
        "summary": "res.summary",
        "link": "res.article_url",
        "image_link": "res.image_link",
        "pub_time": datetime.now(),
        "content": "res.content",
        "chapter_number": 0
    }
    db_intf.store2database(source_info["name"], article)
    a = db_intf.get_top_n_articles_by_key(source_info["name"], 1, source_info["key4sort"])
    for key in article:
        assert a[0][key] == article[key]
