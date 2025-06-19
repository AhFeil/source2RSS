from dataclasses import dataclass
from typing import Self

from pymongo import MongoClient

from src.website_scraper.scraper import ArticleDict, SrcMetaDict

from .db_intf import DatabaseIntf


@dataclass
class MongodbConnInfo:
    mongodb_uri: str
    mongo_dbname: str
    source_meta: str


class MongodbIntf(DatabaseIntf):
    @classmethod
    def connect(cls, info: MongodbConnInfo) -> Self:
        m = MongoClient(info.mongodb_uri)
        db = m[info.mongo_dbname]
        meta_collection = db[info.source_meta]
        return cls(m, db, meta_collection)

    def exist_source_meta(self, source_info: SrcMetaDict):
        source_name = source_info['name']
        may_exist= self.meta_collection.find_one({"name": source_name}, {"_id": 0})
        if not may_exist:
            # 元信息不存在就添加
            self._add_source2meta(source_info)
            self.logger.info(f"{source_name} Add into source_meta")
        elif may_exist != source_info:
            # 元信息不一致就更新
            self.meta_collection.delete_one({"name": source_name})
            self._add_source2meta(source_info)
            self.logger.info(f"{source_name} Update its source_meta")
        else:
            # 元信息保持不变就跳过
            pass

    def store2database(self, source_name: str, one_article_doc: ArticleDict):
        collection = self.db[source_name]
        collection.insert_one(one_article_doc)

    def get_source_info(self, source_name: str) -> SrcMetaDict:
        return self.meta_collection.find_one({"name": source_name}, {"_id": 0})

    def get_top_n_articles_by_key(self, source_name: str, n: int, key: str, reversed: bool=False) -> list[ArticleDict]:
        collection = self.db[source_name]
        result = collection.find({}, {"_id": 0}).sort(key, 1 if reversed else -1).limit(n)
        return list(result)

    def _add_source2meta(self, source_info: SrcMetaDict):
        self.meta_collection.insert_one(source_info)

    def _clear_db(self):
        collections = self.db.list_collection_names()
        # 循环遍历每个集合，并删除其中的所有文档
        for collection_name in collections:
            collection = self.db[collection_name]
            collection.delete_many({})


    def __init__(self, m, db, meta_c):
        super().__init__()
        self.m = m
        self.db = db
        self.meta_collection = meta_c
