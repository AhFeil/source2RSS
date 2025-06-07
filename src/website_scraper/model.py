"""抓取器返回字典定义和 FastAPI 的 Model 等"""
from datetime import datetime
from enum import Enum, StrEnum, IntEnum, auto
from typing import TypedDict, Required, Union, Optional, get_type_hints

from pydantic import BaseModel, HttpUrl, ConfigDict, field_validator


def init_field_names(cls):
    """装饰器：在类定义时自动初始化并存储所有字段名称"""
    if not hasattr(cls, '__field_names__'):
        cls.__field_names__ = set(get_type_hints(cls, include_extras=True).keys())
    return cls


class Sequence(Enum):
    PREFER_NEW2OLD = auto()
    MUST_NEW2OLD = auto()
    PREFER_OLD2NEW = auto()
    MUST_OLD2NEW = auto()


class AccessLevel(IntEnum):
    """源信息可定义访问级别，限制低级别用户查看。主要为用于API发布RSS。数字不能更改，否则需要删除数据库"""
    PUBLIC = 1
    ADMIN = 9


class SortKey(StrEnum):
    PUB_TIME = auto()
    CHAPTER_NUMBER = auto()
    TIME4SORT = auto()
    NUM4SORT = auto()


class LocateInfo(TypedDict, total=False):
    article_title: Required[str]
    pub_time: Required[datetime]
    chapter_number: int
    time4sort: datetime
    num4sort: int
    # 如果 amount 有值，则返回指定数目的最新文章，忽略其他字段
    amount: int


@init_field_names
class SrcMetaDict(TypedDict):
    name: str
    link: str
    desc: str
    lang: str
    key4sort: SortKey
    access: AccessLevel


class SourceMeta(BaseModel):
    model_config = ConfigDict(
        json_encoders={HttpUrl: lambda v: str(v)}, # type: ignore  # 自动将HttpUrl转为字符串
        populate_by_name=True
    )

    name: str
    link: HttpUrl
    desc: str
    lang: str = "zh-CN"
    key4sort: SortKey = SortKey.PUB_TIME
    access: AccessLevel = AccessLevel.PUBLIC


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


class PublishMethod(BaseModel):
    source_name: str | None = None
    key4sort: SortKey = SortKey.PUB_TIME
