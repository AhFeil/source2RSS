import os
from datetime import datetime
import logging

from ruamel.yaml import YAML
from pymongo import MongoClient


class Data:
    def __init__(self, config) -> None:
        self.config = config
        self.logger = logging.getLogger("dataHandle")
        self.yaml = YAML()

        # MongoDB
        self.m = MongoClient(config.mongodb_uri)
        self.db = self.m[config.mongo_dbname]


    def store2database(self, mp_name: str, one_article_doc: dict):
        """将原始 msg、文章信息和时间戳存入数据库"""
        collection = self.db[mp_name]
        collection.insert_one(one_article_doc)

    def add_source2meta(self, source_info: dict):
        """添加某个来源的元信息
        source_info = {
            "title": "",
            "link": "",
            "description": "",
            "language": ""
        }
        """
        collection = self.db[self.config.source_meta]
        collection.insert_one(source_info)
        self.logger.info(f"{source_info['title']} Add into source_meta")

    def _clear_db(self):
        # 清空 collection，仅开发时使用
        collections = self.db.list_collection_names()
        # 循环遍历每个集合，并删除其中的所有文档
        for collection_name in collections:
            collection = self.db[collection_name]
            collection.delete_many({})


if __name__ == "__main__":
    import preprocess

    config = preprocess.config
    data = preprocess.data

