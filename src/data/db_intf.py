import logging
from abc import ABC, abstractmethod

from src.website_scraper.example import SrcMetaDict, ArticleDict


class DatabaseIntf(ABC):
    # 公开接口
    @classmethod
    @abstractmethod
    def connect(cls):
        raise NotImplemented

    @abstractmethod
    def exist_source_meta(self, source_info: SrcMetaDict):
        """确保存在元信息"""
        raise NotImplemented

    @abstractmethod
    def store2database(self, source_name: str, one_article_doc: ArticleDict):
        """将文章信息存入数据库"""
        raise NotImplemented

    @abstractmethod
    def get_source_info(self, source_name: str) -> SrcMetaDict:
        """根据源名称返回源的元信息"""
        raise NotImplemented

    @abstractmethod
    def get_top_n_articles_by_key(self, source_name: str, n: int, key: str, reversed: bool=False) -> list[ArticleDict]:
        """根据 key 排序，默认按照从新到旧，从大到小，返回最前面的若干条"""
        raise NotImplemented

    @abstractmethod
    def _clear_db(self):
        """清空数据库"""
        raise NotImplemented

    # 内部接口
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
