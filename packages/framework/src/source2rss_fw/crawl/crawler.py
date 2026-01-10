import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Self
from zoneinfo import ZoneInfo

from source2rss_fw.plugin import Plugins
from source2rss_fw.scraper import AsyncBrowserManager, WebsiteScraper

from .model import ScraperNameAndParams
from .crawl_error import CrawlRepeatError
from .local_publish import goto_uniform_flow


@dataclass
class Crawler:
    wait_before_close_browser: int
    refractory_period: float
    local_timezone: ZoneInfo
    data: Any

    running_scrapers: set[ScraperNameAndParams]

    @classmethod
    def create(cls, wait_before_close_browser, refractory_period: float, local_timezone: ZoneInfo, data) -> Self:
        return cls(wait_before_close_browser, refractory_period, local_timezone, data, set())

    def has_scraper(self, scraper: ScraperNameAndParams) -> bool:
        if scraper.name == "Representative":
            return False
        return scraper in self.running_scrapers

    def add_scraper(self, scraper: ScraperNameAndParams):
        if scraper.name == "Representative":
            return
        self.running_scrapers.add(scraper)

    async def discard_scraper(self, scraper: ScraperNameAndParams):
        if scraper.name == "Representative":
            return
        await asyncio.sleep(self.refractory_period)
        self.running_scrapers.discard(scraper)

    async def get_scraper_instance(self, scraper: ScraperNameAndParams) -> WebsiteScraper | None:
        """
        对于单例抓取器，同一时间只能有一个在运行，因此有运行时的实例时，新请求引发异常
        对于多实例抓取器，参数相同的情况同上，参数不同的可以有多个
        对于 Remote ，规则同上
        对于 Representative ，不限制
        """
        cls: type[WebsiteScraper] | None = Plugins.get_plugin_or_none(scraper.name)
        # 根本无法创建，返回 None TODO 是否引发异常更合适
        if cls is None or (not scraper.init_params and cls.is_variety):
            return
        # 可以创建，但是重复：有另一个相同的在运行，引发异常
        if self.has_scraper(scraper):
            raise CrawlRepeatError(f"repeat instance of {scraper.name}")
        # 最终创建实例
        self.add_scraper(scraper)  # 需要保证每一处调用该函数的地方都能正常移除
        try:
            if not scraper.init_params:
                instance = await cls.create()
            elif isinstance(scraper.init_params, tuple | list):
                instance = await cls.create(*scraper.init_params)
            else:
                instance = await cls.create(scraper.init_params)
        except Exception:
            # 如果创建失败，短时间内另一个也不一定能成功，因此依然等待
            asyncio.create_task(self.discard_scraper(scraper))
            raise
        return instance

    async def process_one_scraper(self, scraper: ScraperNameAndParams) -> str | None:
        # TODO 在执行之前进行频率检查，如同一网站应该有所间隔
        instance = await self.get_scraper_instance(scraper)
        if instance is None:
            return

        try:
            source_name = await goto_uniform_flow(self.data, instance, scraper, self.local_timezone)
        finally:
            asyncio.create_task(self.discard_scraper(scraper))
            await instance.destroy()  # TODO 不能保证一定会清理资源
        return source_name

    async def process_one_kind_of_class(self, scrapers: tuple[ScraperNameAndParams, ...]) -> list[str]:
        res = []
        # 如果有一个发送异常，剩下的多半也会，因此不继续进行
        for scraper in scrapers:
            source_name = await self.process_one_scraper(scraper)
            if source_name:
                res.append(source_name)
                await asyncio.sleep(scraper.interval)
        return res

    async def process_scraper_groups(self, scraper_groups: Iterable[tuple[ScraperNameAndParams, ...]]) -> list[list[str]]:
        tasks = (self.process_one_kind_of_class(scraper_group) for scraper_group in scraper_groups if scraper_group)
        res = await asyncio.gather(*tasks)
        asyncio.create_task(AsyncBrowserManager.delayed_clean("crawler", self.wait_before_close_browser))  # 兜底 playwright 打开的浏览器被关闭
        return res
