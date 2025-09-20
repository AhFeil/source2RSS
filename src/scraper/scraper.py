import logging
from abc import ABC, ABCMeta, abstractmethod
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta
from typing import Any, ClassVar, Self

from api._v2 import Plugins

from .model import (
    AccessLevel,
    ArticleDict,
    ArticleInfo,
    LocateInfo,
    Sequence,
    SortKey,
    SourceMeta,
    SrcMetaDict,
)


class ScraperMeta(ABCMeta):
    """元类，用于自动注册插件类"""
    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        if name == "WebsiteScraper":  # 此时 WebsiteScraper 还未定义，下面的不能执行
            return
        if not issubclass(cls, WebsiteScraper):
            return
        if not getattr(cls, 'readable_name', None):
            cls.readable_name = name
        cls._logger = logging.getLogger(name)
        # 排除基类自身
        if name != "WebsiteScraper":
            if ScraperMeta._is_init_overridden(cls):
                cls.is_variety = True
            else:
                cls.is_variety = False
            if ScraperMeta._is_parse_old2new_overridden(cls):
                cls.support_old2new = True
            else:
                cls.support_old2new = False
            Plugins.register(name, cls)

    @staticmethod
    def _is_init_overridden(cls_instance):
        return '__init__' in cls_instance.__dict__

    @staticmethod
    def _is_parse_old2new_overridden(cls_instance):
        return '_parse_old2new' in cls_instance.__dict__


class WebsiteScraper(ABC, metaclass=ScraperMeta):

    # ***公开属性***
    # 下面属性由元类自动判别赋值
    is_variety: bool = False   # 创建时是否需要传入额外参数
    support_old2new: bool = False

    # ***对外接口***
    @classmethod
    async def create(cls, *args) -> Self:
        """
        创建抓取器实例的工厂函数。

        Args:
            无参数

        Examples:
            instance = WebsiteScraper.create(*args)
            instance.source_info
        """
        return cls(*args)

    async def destroy(self):
        """用完实例后，进行某些资源的释放，比如锁"""
        pass

    @property
    def source_info(self) -> SrcMetaDict:
        """数据库要有一个表保存每个网站的元信息，生成 RSS 使用"""
        return WebsiteScraper._standardize_src_Info(self._source_info())

    @property
    def max_wait_time(self) -> int:
        """返回在本次执行中，从执行开始到结束占用最长时间，单位秒"""
        return self.__class__.page_turning_duration * 20

    async def get(self, flags: LocateInfo, sequence=Sequence.PREFER_NEW2OLD) -> AsyncGenerator[ArticleDict, None]:
        """获取文章对外接口。若重写本方法，需要保证返回的字典中不能有 ArticleDict 之外的字段"""
        cls = self.__class__
        if amount := flags.get("amount"):
            # 首次运行时用，按从新到旧返回最新的若干条
            if amount <= 0:
                return
            async for a in cls._parse(flags, *self._custom_parameter_of_parse()):
                amount -= 1
                yield WebsiteScraper._standardize_article(a)
                if amount <= 0:
                    return
            return

        key4sort = self.source_info["key4sort"]
        if flags.get(key4sort) is None:
            if cls.support_old2new:
                cls._logger.warning(f"{self.source_info['name']}: flags need {key4sort} for old2new")
                return
            else:
                cls._logger.warning(f"{self.source_info['name']}: flags need {key4sort}")

        if sequence is Sequence.MUST_OLD2NEW:
            async_gen = cls._parse_old2new if cls.support_old2new else \
                        await WebsiteScraper._force_old2new(cls._parse, flags, key4sort, *self._custom_parameter_of_parse())
        elif sequence is Sequence.PREFER_OLD2NEW:
            async_gen = cls._parse_old2new if cls.support_old2new else cls._parse
        else:
            async_gen = cls._parse

        async for a in async_gen(flags, *self._custom_parameter_of_parse()):
            if a[key4sort.value] > flags[key4sort.value]:
                yield WebsiteScraper._standardize_article(a)
            else:
                if cls.support_old2new:
                    continue
                else:
                    return

    # ***内部方法和属性***
    home_url = "https://yanh.tech/"
    # 请求每页之间的间隔，秒
    page_turning_duration = 5
    _logger: ClassVar[logging.Logger]

    @abstractmethod
    def _source_info(self) -> dict:
        return {
            "name": "技焉洲",
            "link": self.__class__.home_url,
            "desc": "Linux，单片机，编程",
            "lang": "zh-CN",
            "tags": "blog\ntechnique\n博客\n技术",
            "key4sort": SortKey.PUB_TIME,
            "access": AccessLevel.USER,
            "table_name": "技焉洲",
        }

    def _custom_parameter_of_parse(self) -> tuple:
        """调用 _parse 时，额外需要提供的参数"""
        return ()

    @classmethod
    @abstractmethod
    async def _parse(cls, flags: LocateInfo, *args) -> AsyncGenerator[dict, None]:
        """按从新到旧，每次返回一条，直到遇到和标记一样的一条，框架不保证传入的 flags 有指定字段"""
        yield {}
        raise NotImplementedError
    # 网站结构一般是链式的，不支持随机索引，而从新到旧的顺序一般都能满足，但是这种顺序一旦中断就无法自发恢复遗漏的
    # 如果支持从旧到新的索引，可以重写 _parse_old2new ，会优先选择；
    @classmethod
    async def _parse_old2new(cls, flags: LocateInfo, *args) -> AsyncGenerator[dict, None]: # noqa: ARG003
        """按从旧到新，从和标记一样的下一条开始返回，每次一条，直到最新，框架保证传入的 flags 中指定字段不为None"""
        yield {}
        raise NotImplementedError

    @staticmethod
    async def _force_old2new(new2old_gen, flags: LocateInfo, key4sort, *args):
        WebsiteScraper._logger.info("start _force_old2new")
        articles = []
        async for a in new2old_gen(flags, *args):
            if a[key4sort] > flags[key4sort]:
                articles.append(a)
            else:
                break
        async def func(*args) -> AsyncGenerator[dict, None]:
            for a in reversed(articles):
                yield a
        return func

    @staticmethod
    def _standardize_article(a: dict) -> ArticleDict:
        return ArticleInfo(**a).model_dump() # type: ignore

    @staticmethod
    def _standardize_src_Info(s: dict) -> SrcMetaDict:
        return SourceMeta(**s).model_dump() # type: ignore

    @staticmethod
    def _get_time_obj(reverse: bool=False, count: int=100, interval: int=2, current_time: datetime | None=None) -> Generator[datetime, None, None]:
        """生成时间对象序列，默认时间越来越新，具体是每次增加 2 分钟，reverse=True时间越来越旧"""
        current_time = current_time or datetime.now()
        step = interval * (-1 if reverse else 1)
        return (current_time + timedelta(minutes=step * n) for n in range(count))

    @staticmethod
    def _range_by_desc_of(elems, flag, compare_func) -> Generator[Any, None, None]:
        """传入列表和标志，默认从列表中匹配标志的元素开始返回，直到列表首元素。当标志与新元素对比，比较函数返回真（大于0的数），否则返回假（0）"""
        for i, elem in enumerate(elems):  # noqa: B007
            if compare_func(elem, flag):
                continue
            break
        else:
            i += 1
        i -= 1
        while i >= 0:
            yield elems[i]
            i -= 1

    @staticmethod
    def _range_by_asc_of(elems, flag, compare_func) -> Generator[Any, None, None]:
        """类似 _range_by_desc_of ，适用于列表的顺序是从旧到新的"""
        for i, elem in enumerate(reversed(elems), start=1):  # noqa: B007
            if compare_func(elem, flag):
                continue
            break
        else:
            i += 1
        i -= 1
        while i > 0:
            yield elems[-i]
            i -= 1
