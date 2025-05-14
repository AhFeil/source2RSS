import logging
from urllib.parse import quote
import asyncio
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import Generator, AsyncGenerator, Any
from typing import TypedDict

import httpx
from playwright.async_api import async_playwright


class FailtoGet(Exception):
    pass

class LocateInfo(TypedDict):
    article_name: str
    pub_time: datetime | None = None
    time4sort: datetime | None = None
    chapter_number: int | None = None

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
            await self.context.close()
            AsyncBrowserManager._users -= 1
            # 所有用户都退出后清理资源
            if AsyncBrowserManager._users == 0 and AsyncBrowserManager._browser is not None:
                await AsyncBrowserManager._browser.close()
                await AsyncBrowserManager._playwright.stop()
                AsyncBrowserManager._browser = None
                AsyncBrowserManager._playwright = None
                AsyncBrowserManager._logger.info("destroy browser by " + self.id)

    @staticmethod
    async def get_html_or_none(id, url, user_agent):
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


class WebsiteScraper(ABC):
    title = "技焉洲"
    home_url = "https://yanh.tech/"
    admin_url = "https://yanh.tech/wp-content"
    # 请求每页之间的间隔，秒
    page_turning_duration = 5
    key4sort = "pub_time"

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

    @property
    @abstractmethod
    def source_info(self):
        """数据库要有一个表或集合保存每个网站的元信息，生成 RSS 使用"""
        return {
            "title": self.__class__.title,
            "link": self.__class__.home_url,
            "description": "Linux，单片机，编程",
            "language": "zh-CN",
            "key4sort": self.__class__.key4sort}

    @property
    def table_name(self):
        """返回表名或者collection名称，以及用于 RSS 文件的名称"""
        return self.source_info["title"]

    @property
    def max_wait_time(self):
        """返回在本次执行中，从执行开始到结束占用最长时间，单位秒"""
        return self.__class__.page_turning_duration * 20
    
    @classmethod
    @abstractmethod
    async def parse(cls, logger, start_page: int=1) -> AsyncGenerator[dict, Any]:
        """按照从新到旧的顺序返回"""
        while True:
            varied_query_dict = {"pagination[page]": start_page}
            query = '&'.join(f"{key}={value}" for key, value in varied_query_dict.items())
            encoded_query = quote(query, safe='[]=&')
            url = "https://admin.bentoml.com/api/blog-posts?" + encoded_query
            logger.info(f"{cls.title} start to parse page {start_page}")
            # 若出现 FailtoGet，则由调度那里接收并跳过
            response = await cls.request(url)

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
                    "article_name": name,
                    "summary": description,
                    "article_url": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj
                }

                yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)

    @classmethod
    async def request(cls, url: str, verify=True) -> httpx.Response | None:
        async with httpx.AsyncClient(follow_redirects=True, verify=verify) as client:
            try:
                response = await client.get(url=url, headers=cls.headers)
            except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout):
                raise FailtoGet
        return response

    @staticmethod
    def get_time_obj(reverse: bool = False, count: int = 20, interval: int = 2) -> Generator[datetime, None, None]:
        """生成时间对象序列，默认时间越来越新，具体是每次增加 2 分钟，reverse=True时间越来越旧"""
        current_time = datetime.now()
        step = interval * (-1 if reverse else 1)
        return (current_time + timedelta(minutes=step * n) for n in range(count))

    def custom_parameter_of_parse(self) -> list:
        """调用 parse 时，额外需要提供的参数"""
        return []

    async def first_add(self, amount: int = 10):
        """接口.第一次添加时用的，比如获取最新的 10 条"""
        if amount <= 0:
            return
        async for a in self.__class__.parse(self.logger, *self.custom_parameter_of_parse()):
            amount -= 1
            yield a
            if amount <= 0:
                return

    async def get_new(self, flags: LocateInfo):
        """接口.第一次添加时，要调用的接口"""
        async for a in self.__class__.parse(self.logger, *self.custom_parameter_of_parse()):
            if a[self.__class__.key4sort] > flags[self.__class__.key4sort]:
                yield a
            else:
                return
