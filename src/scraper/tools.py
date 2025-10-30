"""WebsiteScraper 可以使用的工具"""
import asyncio
import logging
from urllib.robotparser import RobotFileParser

import httpx
from playwright.async_api import TimeoutError as PwTimeoutError
from playwright.async_api import async_playwright

from configHandle import config

logger = logging.getLogger(__name__)


async def get_response_or_none(url: str, headers=None, params=None, verify=True, retry: int=0, timeout: int=10) -> httpx.Response | None:
    backoff_factor: float = 0.5   # 指数退避因子
    async with httpx.AsyncClient(follow_redirects=True, verify=verify, timeout=timeout) as client:
        for attempt in range(retry + 1):  # 包含首次请求
            try:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise httpx.HTTPStatusError("Retryable status code", request=response.request, response=response)
            except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPStatusError) as e:
                if attempt == retry:
                    logger.warning("exception occurred when call get_response_or_none, url is '%s', e is '%s'", url, str(e))
                    return None
                wait_time = backoff_factor * (2 ** attempt)
                await asyncio.sleep(min(wait_time, 60))  # 上限60秒
            except Exception as e:
                msg = f"exception occurred when call get_response_or_none, url is '{url}', e is '{e}'"
                logger.error(msg)
                await config.post2RSS("error log of get_response_or_none", msg)
                return None
            else:
                return response


class AsyncBrowserManager:
    """被多个事件循环调用时会出错"""
    _browser = None
    _playwright = None
    _users = 0
    _users_that_is_waiting = 0
    _lock = asyncio.Lock()
    _logger = logging.getLogger("AsyncBrowserManager")

    def __init__(self, id_: str, user_agent=None):
        self.id_ = id_
        self.user_agent = user_agent
        self.context = None

    async def __aenter__(self):
        # 协程并发下，如果不加锁，有可能会实例化多个 _browser 或其他非预期状况
        async with AsyncBrowserManager._lock:
            # 首次使用时初始化浏览器和 Playwright
            if AsyncBrowserManager._browser is None:
                AsyncBrowserManager._playwright = await async_playwright().start()
                AsyncBrowserManager._browser = await AsyncBrowserManager._playwright.chromium.launch(headless=True)
                AsyncBrowserManager._logger.info("create browser for " + self.id_)
        await AsyncBrowserManager.waiting_operation(self.id_, config.max_opening_context)
        self.context = await AsyncBrowserManager._browser.new_context(
            viewport={"width": 1920, "height": 1080}, accept_downloads=True, user_agent=self.user_agent
        )
        AsyncBrowserManager._logger.debug("create context for " + self.id_)
        return self.context

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with AsyncBrowserManager._lock:
            await self.context.close() # type: ignore
            AsyncBrowserManager._logger.debug("destroy context of " + self.id_)
            AsyncBrowserManager._users -= 1
            # 所有用户都退出后清理资源
        asyncio.create_task(AsyncBrowserManager.delayed_clean(self.id_, config.wait_before_close_browser))

    @classmethod
    async def delayed_clean(cls, id_, delay: int):
        async with AsyncBrowserManager._lock:
            if cls._users > 0:
                return
        await asyncio.sleep(delay)
        async with AsyncBrowserManager._lock:
            all_users = cls._users + cls._users_that_is_waiting
            if all_users == 0 and cls._browser is not None:
                await cls._browser.close()
                await cls._playwright.stop() # type: ignore
                cls._browser = None
                cls._playwright = None
                cls._logger.info("destroy browser by %s", id_)
            elif all_users > 0:
                cls._logger.info("leave browser alone, said by %s", id_)
            elif all_users == 0 and cls._browser is None:
                pass
            else:
                cls._logger.warning(f"unexpected situcation {id_}, {cls._users=}, {cls._users_that_is_waiting=}, {cls._browser=}")

    @classmethod
    async def waiting_operation(cls, id_, max_: int):
        need_wait = True
        cls._users_that_is_waiting += 1
        while(need_wait):
            async with cls._lock:
                if cls._users >= max_:
                    cls._logger.info("%s need to wait for context", id_)
                    need_wait = True
                else:
                    cls._users += 1
                    need_wait = False
            if need_wait:
                await asyncio.sleep(15)
        cls._users_that_is_waiting -= 1


    @staticmethod
    async def get_html_or_none(id_: str, url: str, user_agent, block_func=None):
        html_content = None
        async with AsyncBrowserManager(id_, user_agent) as context:
            if block_func:
                await context.route("**/*", block_func)
            page = await context.new_page()
            AsyncBrowserManager._logger.debug("create page for " + id_)
            try:
                await page.goto(url, timeout=180000, wait_until='networkidle')   # 单位是毫秒，共 3 分钟
            except PwTimeoutError as e:
                AsyncBrowserManager._logger.warning(f"Page navigation of {id_} timed out: {e}")
            else:
                html_content = await page.content()
            finally:
                await page.close()
                AsyncBrowserManager._logger.debug("destroy page of " + id_)
        return html_content


async def create_rp(robots_txt: str, headers: dict | None = None) -> RobotFileParser:
    """robots_txt 可以是字符串或网址，使用 rp.can_fetch(url) 判断是否能爬取"""
    if robots_txt.startswith("http"):
        res = await get_response_or_none(robots_txt, headers)
        robots_txt = res.text if res else "User-agent: *\nAllow: /"
    rp = RobotFileParser()
    rp.parse(robots_txt.split('\n'))
    return rp
