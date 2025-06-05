"""抓取器返回字典定义和 FastAPI 的 Model 等"""
from datetime import datetime
from enum import Enum
from typing import TypedDict, Required, Union, Optional, get_type_hints

from pydantic import BaseModel, HttpUrl, ConfigDict, field_validator


def init_field_names(cls):
    """装饰器：在类定义时自动初始化并存储所有字段名称"""
    if not hasattr(cls, '__field_names__'):
        cls.__field_names__ = set(get_type_hints(cls, include_extras=True).keys())
    return cls


class LocateInfo(TypedDict, total=False):
    article_title: Required[str]
    pub_time: Required[datetime]
    chapter_number: int
    time4sort: datetime
    num4sort: int
    # 如果 amount 有值，则返回指定数目的最新文章，忽略其他字段
    amount: int
    # old2new 若有值，则调用相应接口
    must_old2new: bool # todo 用枚举更合适
    prefer_old2new: bool


@init_field_names
class SrcMetaDict(TypedDict):
    name: str
    link: str
    desc: str
    lang: str
    key4sort: str


class SourceMeta(BaseModel):
    model_config = ConfigDict(
        json_encoders={HttpUrl: lambda v: str(v)}, # type: ignore  # 自动将HttpUrl转为字符串
        populate_by_name=True
    )

    name: str
    link: HttpUrl
    desc: str
    lang: str = "zh-CN"
    key4sort: str = "pub_time"


@init_field_names
class ArticleDict(TypedDict, total=False):
    id: int
    title: Required[str]
    summary: Required[str]
    link: Required[str]
    image_link: str
    content: str
    pub_time: Required[datetime]
    chapter_number: int   # 用于排序,比如小说按照章节排更合适
    time4sort: datetime
    num4sort: int


class ArticleInfo(BaseModel):
    id: Optional[int] = 0
    title: str
    summary: str
    link: HttpUrl
    pub_time: datetime
    content: Optional[str] = ""
    image_link: Optional[HttpUrl] = "" # todo
    chapter_number: Optional[int] = 0
    time4sort: Optional[datetime] = datetime.now()
    num4sort: Optional[int] = 0

    @field_validator('pub_time', mode='before')
    @classmethod
    def convert_timestamp(cls, v: Union[datetime, int, float]) -> datetime:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        return v

    def model_dump_to_json(self):
        res = self.model_dump()
        res["link"] = str(res["link"])
        res["image_link"] = str(res["image_link"])
        return res


class SortKey(str, Enum):
    pub_date = "pub_date"
    pub_time = "pub_time"
    chapter_number = "chapter_number"

class PublishMethod(BaseModel):
    source_name: str | None = None
    key4sort: SortKey = SortKey.pub_date
