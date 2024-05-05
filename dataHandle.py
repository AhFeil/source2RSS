import os
from datetime import datetime
import logging

from ruamel.yaml import YAML
from pymongo import MongoClient
from enum import Enum
from pydantic import BaseModel, field_validator


class SourceMeta(BaseModel):
    title: str
    link: str = "https://yanh.tech/"
    description: str = f"这是一个 RSS 源， 由 source2RSS 项目程序生成"
    language: str = "zh-CN"

class ArticleInfo(BaseModel):
    article_name: str 
    article_url: str ="https://yanh.tech/"
    pub_time: float = datetime.fromtimestamp(0)  # 时间戳
    summary: str = ""
    image_link: str = "https://yanh.tech/"

    # 上面是 RSS 必需的,下面是补充、辅助的
    # 用于排序,比如小说按照章节排更合适,虽然发布时间理应对应章节顺序 
    chapter: int = 0
    
    @field_validator('pub_time')
    @classmethod
    def timestamp_to_datetime(cls, v):
        return datetime.fromtimestamp(float(v))


class SortKey(str, Enum):
    pub_date = "pub_date"
    chapter = "chapter"

class PublishContent(BaseModel):
    source_name: str
    article_infomation: ArticleInfo
    key4sort: SortKey = SortKey.pub_date


class Data:
    def __init__(self, config) -> None:
        self.config = config
        self.logger = logging.getLogger("dataHandle")
        self.yaml = YAML()

        # MongoDB
        self.m = MongoClient(config.mongodb_uri)
        self.db = self.m[config.mongo_dbname]
        self.meta_collection = self.db[self.config.source_meta]

    def store2database(self, mp_name: str, one_article_doc: dict):
        """将原始 msg、文章信息和时间戳存入数据库"""
        collection = self.db[mp_name]
        collection.insert_one(one_article_doc)

    def get_source_info(self, source_name: str):
        """根据源名称返回源的元信息"""
        return self.meta_collection.find_one({"title": source_name})

    def exist_source_meta(self, source_info: dict):
        # 确保存在元信息
        if not self.meta_collection.find_one({"title": source_info["title"]}):
            self._add_source2meta(source_info)

    def _add_source2meta(self, source_info: dict):
        """添加某个来源的元信息
        source_info = {
            "title": "",
            "link": "",
            "description": "",
            "language": ""
        }
        """
        self.meta_collection.insert_one(source_info)
        self.logger.info(f"{source_info['title']} Add into source_meta")

    def _clear_db(self):
        # 清空 collection，仅开发时使用
        collections = self.db.list_collection_names()
        # 循环遍历每个集合，并删除其中的所有文档
        for collection_name in collections:
            collection = self.db[collection_name]
            collection.delete_many({})


if __name__ == "__main__":
    # import preprocess

    # config = preprocess.config
    # data = preprocess.data

    m = ArticleInfo(title="a title", key4sort="chapter")
    print(m)