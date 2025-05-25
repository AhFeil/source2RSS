from pathlib import Path
from datetime import datetime
import logging

from ruamel.yaml import YAML
from enum import Enum
from pydantic import BaseModel, HttpUrl, field_validator

from src.data import DatabaseIntf, MongodbIntf, MongodbConnInfo

class SourceMeta(BaseModel):
    title: str
    link: HttpUrl = "https://yanh.tech/" # type: ignore
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
    pub_time: datetime = datetime.fromtimestamp(0)  # 时间戳
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

        # DB
        info = MongodbConnInfo(config.mongodb_uri, config.mongo_dbname, config.source_meta)
        self.db_intf: DatabaseIntf = MongodbIntf.connect(info)

    def get_rss_or_None(self, source_file_name: str) -> str | None:
        return self._rss.get(source_file_name)

    def get_rss_list(self) -> list[str]:
        return sorted([rss for rss in self._rss if rss.endswith(".xml")])

    def set_rss(self, source_file_name: str, rss: bytes, cls_id_or_none: str | None):
        """将RSS文件名和RSS内容映射，如果是单例，还将类名和RSS内容映射"""
        rss_str = rss.decode()
        self._rss[source_file_name] = rss_str
        if cls_id_or_none:
            self._rss[cls_id_or_none] = rss_str
        rss_filepath = Path(self.config.rss_dir) / source_file_name
        with open(rss_filepath, 'wb') as rss_file:
            rss_file.write(rss)

    def rss_is_absent(self, source_file_name: str) -> bool:
        return source_file_name not in self._rss

    @staticmethod
    def _load_files_to_dict(directory):
        path = Path(directory)
        file_dict = {}
        for file_path in path.iterdir():  # 遍历目录中的条目
            if file_path.is_file():
                file_content = file_path.read_text(encoding='utf-8')
                file_dict[file_path.name] = file_content
        return file_dict
