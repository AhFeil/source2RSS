import asyncio
import logging
import signal
from dataclasses import dataclass
from typing import Iterable, Self

from configHandle import post2RSS
from preproc import Plugins, config, data
from src.website_scraper import AsyncBrowserManager, WebsiteScraper
from src.website_scraper.scraper_error import (
    CreateByInvalidParam,
    CreateByLocked,
    FailtoGet,
)

from .crawl_error import CrawlInitError
from .local_publish import goto_uniform_flow

logger = logging.getLogger("crawler")


async def _process_one_kind_of_class(data, cls: WebsiteScraper, init_params: Iterable, amount: int) -> list[str]:
    """创建实例然后走统一流程"""
    res = []
    for params in init_params:
        if params is None and cls.is_variety:
            continue
        try:
            if isinstance(params, dict) or isinstance(params, str):
                instance = await cls.create(params)
            elif isinstance(params, list) or isinstance(params, tuple):
                instance = await cls.create(*params)
            else:
                instance = await cls.create()
        except TypeError:
            raise CrawlInitError(400, "The amount of parameters is incorrect")
        except CreateByLocked:
            raise CrawlInitError(422, "Server is busy")
        except CreateByInvalidParam:
            raise CrawlInitError(422, "Invalid parameters")
        except FailtoGet:
            raise CrawlInitError(500, "Failed when crawling")
        except Exception as e:
            msg = f"fail when query rss {cls.__name__}: {e}"
            logger.exception(msg)
            await post2RSS("error log of _process_one_kind_of_class", msg)
            raise CrawlInitError(500, "Unknown Error")
        else:
            try:
                source_name = await goto_uniform_flow(data, instance, amount)
            except Exception as e:
                msg = f"fail when goto_uniform_flow of {source_name}: {e}"
                logger.exception(msg)
                await post2RSS("error log of goto_uniform_flow", msg)
            else:
                res.append(source_name)
            finally:
                instance.destroy()
    return res


@dataclass
class ClassNameAndParams:
    name: str
    init_params: Iterable
    amount: int

    @classmethod
    def create(cls, cls_name: str, init_params: Iterable | None = None, amount: int | None = None) -> Self:
        """如果没有传入初始化参数等，就从配置中去取"""
        init_params = init_params or config.get_params(cls_name)
        amount = amount or config.get_amount(cls_name)
        return cls(cls_name, init_params, amount)


async def start_to_crawl(clses: Iterable[ClassNameAndParams]):
    """根据类名获得相应的类，和它们的初始化参数，组装协程然后放入事件循环"""
    tasks = (_process_one_kind_of_class(data, cls, item.init_params, item.amount) for item in clses if (cls := Plugins.get_plugin_or_none(item.name)))
    res = await asyncio.gather(*tasks)
    asyncio.create_task(AsyncBrowserManager.delayed_clean("crawler", config.wait_before_close_browser)) # 兜底 playwright 打开的浏览器被关闭
    return res


running_lock = asyncio.Lock()

async def start_to_crawl_all():
    global running_lock
    if running_lock.locked():
        logger.info("is crawling now")
        return
    logger.info("***Start all scrapers***")
    async with running_lock:
        try:
            await start_to_crawl(ClassNameAndParams.create(name) for name in Plugins.get_all_id())
        except CrawlInitError as e:
            if e.code == 500:
                raise # 已知的错误就抑制
    logger.info("***Have finished all scrapers***")


if __name__ == "__main__":
    def handler(sig, frame):
        # 退出前清理环境
        exit(0)
    signal.signal(signal.SIGINT, handler)

    asyncio.run(start_to_crawl_all())
    # .env/bin/python -m src.crawl.crawler
