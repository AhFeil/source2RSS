"""FastAPI 和数据库的 Model 等"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, HttpUrl, field_validator, ConfigDict


class SourceMeta(BaseModel):
    # model_config = ConfigDict(
    #     json_encoders={HttpUrl: str},  # 自动将 HttpUrl 转换为字符串
    #     populate_by_name=True
    # )

    name: str
    link: HttpUrl = "https://yanh.tech/" # type: ignore
    desc: str = "这是一个 RSS 源， 由 source2RSS 项目程序生成"
    lang: str = "zh-CN"
    key4sort: str = "pub_time"

    def model_dump(self):
        return {
            "name": self.name,
            "link": str(self.link),
            "desc": self.desc,
            "lang": self.lang,
            "key4sort": self.key4sort
        }


class ArticleInfo(BaseModel):
    id: int
    title: str
    summary: str = ""
    link: HttpUrl | str ="https://yanh.tech/"   # 这个应该是网址或者空字符串
    pub_time: datetime = datetime.fromtimestamp(0)  # 时间戳
    content: str = ""
    image_link: HttpUrl | str = "https://yanh.tech/"
    # 上面是 RSS 必需的,下面是补充、辅助的
    chapter_number: int = 0   # 用于排序,比如小说按照章节排更合适

    def model_dump(self):
        return {
            "id": self.id,
            "name": self.title,
            "summary": self.summary,
            "link": str(self.link),
            "pub_time": self.pub_time,
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
