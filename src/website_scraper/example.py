import logging
from urllib.parse import quote
import asyncio
from datetime import datetime, timedelta
from abc import ABC, ABCMeta, abstractmethod
from typing import Generator, AsyncGenerator, Self, Any

import httpx
from playwright.async_api import async_playwright

import api._v1
from api._v2 import Plugins
from .model import LocateInfo, SrcMetaDict, ArticleDict


class FailtoGet(Exception):
    pass

class CreateByInvalidParam(Exception):
    pass


class AsyncBrowserManager:
    _browser = None
    _playwright = None
    _users = 0
    _lock = asyncio.Lock()
    _logger = logging.getLogger("AsyncBrowserManager")

    def __init__(self, id: str, user_agent=None):
        self.id = id
        self.user_agent = user_agent
        self.context = None

    async def __aenter__(self):
        # 协程并发下，如果不加锁，有可能会实例化多个 _browser 或其他非预期状况
        # 这里加锁并不会导致同时只有一个协程能使用浏览器
        async with AsyncBrowserManager._lock:
            # 首次使用时初始化浏览器和 Playwright
            if AsyncBrowserManager._browser is None:
                AsyncBrowserManager._playwright = await async_playwright().start()
                AsyncBrowserManager._browser = await AsyncBrowserManager._playwright.chromium.launch(headless=True)
                AsyncBrowserManager._logger.info("create browser for " + self.id)
            AsyncBrowserManager._users += 1
        self.context = await AsyncBrowserManager._browser.new_context(viewport={"width": 1920, "height": 1080}, accept_downloads=True, user_agent=self.user_agent)
        return self.context

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with AsyncBrowserManager._lock:
            await self.context.close() # type: ignore
            AsyncBrowserManager._users -= 1
            # 所有用户都退出后清理资源
            if AsyncBrowserManager._users == 0 and AsyncBrowserManager._browser is not None:
                await AsyncBrowserManager._browser.close()
                await AsyncBrowserManager._playwright.stop() # type: ignore
                AsyncBrowserManager._browser = None
                AsyncBrowserManager._playwright = None
                AsyncBrowserManager._logger.info("destroy browser by " + self.id)

    @staticmethod
    async def get_html_or_none(id: str, url: str, user_agent):
        html_content = None
        async with AsyncBrowserManager(id, user_agent) as context:
            page = await context.new_page()
            try:
                await page.goto(url, timeout=180000, wait_until='networkidle')   # 单位是毫秒，共 3 分钟
            except TimeoutError as e:
                AsyncBrowserManager._logger.warning(f"Page navigation of {id} timed out: {e}")
            else:
                html_content = await page.content()
            finally:
                await page.close()
        return html_content


class ScraperMeta(ABCMeta):
    """元类，用于自动注册插件类"""
    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        # 排除基类自身，并确保是PluginBase的子类
        if name != "WebsiteScraper" and issubclass(cls, WebsiteScraper):
            # 获取插件名称（优先使用类属性name，否则使用类名）
            plugin_name = getattr(cls, 'name', name)
            if ScraperMeta._is_init_overridden(cls):
                cls.is_variety = True
                api._v1.register_c(cls)
            else:
                cls.is_variety = False
                api._v1.register(cls)
            if ScraperMeta._is_get_from_old2new_overridden(cls):
                cls.support_old2new = True
            else:
                cls.support_old2new = False   # todo 不重写不一定不行
            Plugins.register(plugin_name, cls)

    @staticmethod
    def _is_init_overridden(cls_instance):
        return '__init__' in cls_instance.__dict__

    @staticmethod
    def _is_get_from_old2new_overridden(cls_instance):
        return 'get_from_old2new' in cls_instance.__dict__


class WebsiteScraper(ABC, metaclass=ScraperMeta):

    # ***公开属性***
    key4sort = "pub_time"
    support_old2new: bool = False # 需要手动指定，为真则调用 old2new 接口
    # 下面属性由元类自动判别赋值
    is_variety: bool = False   # 创建时是否需要传入额外参数

    # ***对外接口***
    @classmethod
    async def create(cls) -> Self:
        return cls()

    @property
    def source_info(self) -> SrcMetaDict:
        """数据库要有一个表保存每个网站的元信息，生成 RSS 使用"""
        return WebsiteScraper._standardize_src_Info(self._source_info())

    @property
    def table_name(self) -> str:
        """返回表名，并会用于 RSS 文件的名称"""
        return self.source_info["name"]

    @property
    def max_wait_time(self) -> int:
        """返回在本次执行中，从执行开始到结束占用最长时间，单位秒"""
        return self.__class__.page_turning_duration * 20

    async def get(self, flags: LocateInfo) -> AsyncGenerator[ArticleDict, None]:
        """获取文章对外接口。重写的话，需要保证返回的字典中不能有 ArticleDict 之外的字段"""
        if amount := flags.get("amount"):
            # 首次运行时用，按从新到旧返回最新的若干条
            if amount <= 0:
                return
            async for a in self.__class__._parse(self.logger, *self._custom_parameter_of_parse()):
                amount -= 1
                yield WebsiteScraper._standardize_article(a)
                if amount <= 0:
                    return

        if flags.get("must_old2new"):
            async_gen = self._get_from_old2new if self.__class__.support_old2new else self._force_get_from_old2new
        elif flags.get("prefer_old2new"):
            async_gen = self._get_from_old2new if self.__class__.support_old2new else self._get_new
        else:
            async_gen = self._get_new
        async for a in async_gen(flags):
            yield WebsiteScraper._standardize_article(a)

    # ***内部方法和属性***
    title = "技焉洲"
    home_url = "https://yanh.tech/"
    admin_url = "https://yanh.tech/wp-content"
    # 请求每页之间的间隔，秒
    page_turning_duration = 5
    # https://curlconverter.com/
    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Content-Type': 'application/json',
        'Origin': 'https://yanh.tech',
        'Referer': 'https://yanh.tech',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    }

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def _source_info(self) -> dict:
        return {
            'name': self.__class__.title,   # todo 考虑不作为类属性
            'link': self.__class__.home_url,
            'desc': "Linux，单片机，编程",
            'lang': "zh-CN",
            'key4sort': self.__class__.key4sort
        }

    @classmethod
    @abstractmethod
    async def _parse(cls, logger) -> AsyncGenerator[dict, None]:
        """按照从新到旧的顺序返回"""
        while True:
            varied_query_dict = {"pagination[page]": start_page}
            query = '&'.join(f"{key}={value}" for key, value in varied_query_dict.items())
            encoded_query = quote(query, safe='[]=&')
            url = "https://admin.bentoml.com/api/blog-posts?" + encoded_query
            logger.info(f"{cls.title} start to parse page {start_page}")
            # 若出现 FailtoGet，则由调度那里接收并跳过
            response = await cls._request(url)

            # 初次适配使用，保存网站数据
            # with open("for_test.html", 'w', encoding='utf-8') as f:
            #     f.write(response.text)
            # break
            # 初次适配使用，读取网站数据
            # with open("for_test.html", 'r', encoding='utf-8') as f:
            #     response_text = f.read()

            articles = response.json()
            # 超出结尾了
            if not articles["data"]:
                return

            for a in articles["data"]:
                id = a["id"]
                attributes = a["attributes"]
                name = attributes["name"]
                description = attributes["description"]
                slug = attributes["slug"]
                article_url = cls.home_url + '/' + slug
                image = attributes["image"]
                image_link = cls.admin_url + image["data"]["attributes"]["url"]
                create_time = image["data"]["attributes"]["createdAt"]
                time_obj = datetime.strptime(create_time, "%Y-%m-%dT%H:%M:%S.%fZ")

                article = {
                    "id": id,
                    "title": name,
                    "summary": description,
                    "link": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj,
                }
                yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)

    def _custom_parameter_of_parse(self) -> list:
        """调用 _parse 时，额外需要提供的参数"""
        return []

    async def _get_new(self, flags: LocateInfo) -> AsyncGenerator[dict, None]:
        """按从新到旧，每次返回一条，直到遇到和标记一样的一条"""
        key4sort = self.__class__.key4sort
        if flags.get(key4sort) is None:
            self.logger.error(f"{self.source_info['name']}: flags need {key4sort}")
        async for a in self.__class__._parse(self.logger, *self._custom_parameter_of_parse()):
            if a[key4sort] > flags[key4sort]:
                yield a
            else:
                return
    # 网站结构一般是链式的，不支持随机索引，而从新到旧的顺序一般都能满足，但是这种顺序一旦中断就无法自发恢复遗漏的
    # 如果支持从旧到新的索引，可以覆写 get_from_old2new ，会优先选择；若不支持但希望保证数据不缺失，也可以覆写，使用 super() 调一次父类方法即可
    async def _get_from_old2new(self, flags: LocateInfo) -> AsyncGenerator[dict, None]:
        """按从旧到新，从和标记一样的下一条开始返回，每次一条，直到最新"""
        key4sort = self.__class__.key4sort
        if flag := flags.get(key4sort):
            async for a in self.__class__._parse(self.logger, *self._custom_parameter_of_parse(), flag): # type: ignore
                yield a
        else:
            self.logger.error(f"{self.source_info['name']}: flags need {key4sort} for old2new")

    async def _force_get_from_old2new(self, flags: LocateInfo) -> AsyncGenerator[dict, None]:
        articles = []
        async for a in self._get_new(flags):
            articles.append(a)
        for a in reversed(articles):
            yield a

    @classmethod
    async def _request(cls, url: str, verify=True) -> httpx.Response:
        async with httpx.AsyncClient(follow_redirects=True, verify=verify) as client:
            try:
                response = await client.get(url=url, headers=cls.headers)
            except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout):
                raise FailtoGet
            else:
                return response

    @staticmethod
    def _standardize_article(a: dict) -> ArticleDict:
        extra_keys = set(a.keys()) - ArticleDict.__field_names__ # type: ignore
        for k in extra_keys:
            a.pop(k)
        return a # type: ignore

    @staticmethod
    def _standardize_src_Info(s: dict) -> SrcMetaDict:
        extra_keys = set(s.keys()) - SrcMetaDict.__field_names__ # type: ignore
        for k in extra_keys:
            s.pop(k)
        return s # type: ignore

    @staticmethod
    def _get_time_obj(reverse: bool = False, count: int = 100, interval: int = 2) -> Generator[datetime, None, None]:
        """生成时间对象序列，默认时间越来越新，具体是每次增加 2 分钟，reverse=True时间越来越旧"""
        current_time = datetime.now()
        step = interval * (-1 if reverse else 1)
        return (current_time + timedelta(minutes=step * n) for n in range(count))

    @staticmethod
    def _range_by_desc_of(elems, flag, compare_func) -> Generator[Any, None, None]:
        """传入列表和标志，默认从列表中匹配标志的元素开始返回，直到列表首元素。当标志与新元素对比，比较函数返回真（大于0的数），否则返回假（0）"""
        for i, elem in enumerate(elems):
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
        for i, elem in enumerate(reversed(elems), start=1):
            if compare_func(elem, flag):
                continue
            break
        else:
            i += 1
        i -= 1
        while i > 0:
            yield elems[-i]
            i -= 1
