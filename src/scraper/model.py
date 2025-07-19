"""抓取器返回字典定义和 FastAPI 的 Model 等"""
from datetime import datetime
from enum import Enum, IntEnum, StrEnum, auto
from typing import Optional, Required, TypedDict, Union, get_type_hints

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator


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
    NONE = 0          # 任何请求者都能查看
    PUBLIC = 1        # 任何请求者都能查看

    SHARED_USER = 3   # 所有用户都能查看这个级别的内容
    LIMITED_USER = 4  # （未实现）被授权的用户才能查看，创建者默认被授权，并可以授权给别人，但别人不能再次授权
    USER = 5          # 被授权的用户才能查看，由管理员授权，被授权者不能授权别人
    PRIVATE_USER = 6  # （未实现）仅创建者可以查看，有管理员权限也不能查看

    SYSTEM = 8        # 定期运行的属于系统级别
    ADMIN = 9         # 管理员，就是那个可以关停程序、修改配置文件和数据库文件的人
    # DEV = 10        # 最高级别是开发，但是开发只能在代码里写死，不能影响已上线的程序


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
        frozen=True,
        json_encoders={HttpUrl: lambda v: str(v)}, # type: ignore  # 自动将HttpUrl转为字符串
        populate_by_name=True
    )

    name: str
    link: str # HttpUrl 不能和字符串进行比较，不能被数据库用时自动转换为字符串，太不好用
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
    model_config = ConfigDict(frozen=True)

    id: Optional[int] = 0
    title: str
    summary: str
    link: str
    pub_time: datetime
    content: Optional[str] = ""
    image_link: Optional[str] = ""
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
