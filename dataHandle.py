from pathlib import Path
from datetime import datetime
import logging

from ruamel.yaml import YAML
from pymongo import MongoClient
from enum import Enum
from pydantic import BaseModel, HttpUrl, field_validator


class SourceMeta(BaseModel):
    title: str
    link: HttpUrl = "https://yanh.tech/"
    description: str = f"这是一个 RSS 源， 由 source2RSS 项目程序生成"
    language: str = "zh-CN"
    key4sort: str = "pub_time"

    def model_dump(self):
        return {
            "title": self.title,
            "link": str(self.link),
            "description": self.description,
            "language": self.language,
            "key4sort": self.key4sort
        }

class ArticleInfo(BaseModel):
    article_name: str 
    article_url: HttpUrl | str ="https://yanh.tech/"   # 这个应该是网址或者空字符串
    pub_time: float = datetime.fromtimestamp(0)  # 时间戳
    summary: str = ""
    content: str = ""
    image_link: HttpUrl | str = "https://yanh.tech/"
    # 上面是 RSS 必需的,下面是补充、辅助的
    chapter_number: int = 0   # 用于排序,比如小说按照章节排更合适

    def model_dump(self):
        return {
            "article_name": self.article_name,
            "article_url": str(self.article_url),
            "pub_time": self.pub_time,
            "summary": self.summary,
            "content": self.content,
            "image_link": str(self.image_link),
            "chapter_number": self.chapter_number
        }
    
    @field_validator('pub_time')
    @classmethod
    def timestamp_to_datetime(cls, v):
        return datetime.fromtimestamp(float(v))


class SortKey(str, Enum):
    pub_date = "pub_date"
    pub_time = "pub_time"
    chapter_number = "chapter_number"

class PublishMethod(BaseModel):
    source_name: str | None = None
    key4sort: SortKey = SortKey.pub_date


class Data:
    def __init__(self, config) -> None:
        self.config = config
        self.logger = logging.getLogger("dataHandle")
        self.yaml = YAML()

        # 内存里的RSS数据
        self._rss: dict[str, str] = Data._load_files_to_dict(config.rss_dir)

        # MongoDB
        self.m = MongoClient(config.mongodb_uri)
        self.db = self.m[config.mongo_dbname]
        self.meta_collection = self.db[self.config.source_meta]

    def get_rss_or_None(self, source_file_name: str) -> str | None:
        return self._rss.get(source_file_name)

    def get_rss_list(self) -> list[str]:
        return sorted([rss for rss in self._rss])

    def set_rss(self, source_file_name: str, rss: str):
        self._rss[source_file_name] = rss
        rss_filepath = Path(self.config.rss_dir) / source_file_name
        with open(rss_filepath, 'wb') as rss_file:
            rss_file.write(rss)

    def rss_is_absent(self, source_file_name: str) -> bool:
        return source_file_name not in self._rss

    def store2database(self, mp_name: str, one_article_doc: dict):
        """将原始 msg、文章信息和时间戳存入数据库"""
        collection = self.db[mp_name]
        collection.insert_one(one_article_doc)

    def get_source_info(self, source_name: str):
        """根据源名称返回源的元信息"""
        return self.meta_collection.find_one({"title": source_name})

    def exist_source_meta(self, source_info: dict):
        # 确保存在元信息
        may_exist= self.meta_collection.find_one({"title": source_info["title"]}, {"_id": 0})
        if not may_exist:
            # 元信息不存在就添加
            self._add_source2meta(source_info)
            self.logger.info(f"{source_info['title']} Add into source_meta")
        elif may_exist != source_info:
            # 元信息不一致就更新
            self.meta_collection.delete_one({"title": source_info["title"]})
            self._add_source2meta(source_info)
            self.logger.info(f"{source_info['title']} Update its source_meta")
        else:
            # 元信息保持不变就跳过
            pass

    def _add_source2meta(self, source_info: dict):
        """添加某个来源的元信息
        source_info = {
            "title": "",
            "link": "",
            "description": "",
            "language": ""
            "key4sort": ""
        }
        """
        self.meta_collection.insert_one(source_info)

    def _clear_db(self):
        # 清空 collection，仅开发时使用
        collections = self.db.list_collection_names()
        # 循环遍历每个集合，并删除其中的所有文档
        for collection_name in collections:
            collection = self.db[collection_name]
            collection.delete_many({})

    @staticmethod
    def _load_files_to_dict(directory):
        path = Path(directory)
        file_dict = {}
        for file_path in path.iterdir():  # 遍历目录中的条目
            if file_path.is_file():
                file_content = file_path.read_text(encoding='utf-8')
                file_dict[file_path.name] = file_content
        return file_dict
