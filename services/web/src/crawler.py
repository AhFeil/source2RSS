import asyncio
import logging
from collections.abc import Iterable

from pydantic_core import ValidationError

from source2rss_fw.crawl import ScraperNameAndParams, Crawler
from source2rss_fw.crawl.crawl_error import CrawlError, CrawlInitError, CrawlRunError
from source2rss_fw.scraper.scraper_error import (
    CreateButRequestFail,
    CreateByInvalidParam,
    CreateByLackAgent,
    CreateByLocked,
    FailtoGet,
)

from .config_handle import config
from .data_handle import data, Plugins

logger = logging.getLogger("crawler")

crawler = Crawler.create(config.wait_before_close_browser, config.refractory_period, config.timezone, data)


def create_scraper_name_and_params(
    cls_name: str, init_params_es: Iterable | None = None, amount: int | None = None, i_am_remote: bool = False
) -> tuple[ScraperNameAndParams, ...]:
    # 如果未提供参数，就从配置中取
    return ScraperNameAndParams.create(
        cls_name,
        init_params_es or config.get_params(cls_name),
        amount or config.get_amount(cls_name),
        config.get_max_rss_items(cls_name),
        config.get_interval(cls_name),
        config.get_prefer_agent,
        data.agents.get,
        i_am_remote,
    )


EXCEPTION_MAP: list[tuple[type[Exception], Exception]] = [
    (TypeError, CrawlInitError(400, "The amount of parameters is incorrect")),
    (CreateByLocked, CrawlInitError(423, "Server is busy")),
    (CreateByInvalidParam, CrawlInitError(422, "Invalid parameters")),
    (CreateByLackAgent, CrawlInitError(423, "Lack agent")),
    (CreateButRequestFail, CrawlInitError(503, "Failed when crawling")),  # todo 多次连续出现，则 post2RSS
    (FailtoGet, CrawlInitError(503, "Failed when crawling")),
    # 下面是 goto_uniform_flow 的异常
    (ValidationError, CrawlRunError(422, "Invalid source meta")),
]


async def run_with_crawl_error(coro, scraper: ScraperNameAndParams):
    try:
        return await coro
    except Exception as e:
        for exc_type, mapped in EXCEPTION_MAP:
            if isinstance(e, exc_type):
                raise mapped from e
        if isinstance(e, CrawlError):
            raise
        msg = f"fail when query rss {scraper.name}, {scraper.init_params=}: {e}"
        logger.exception(msg)
        await config.post2RSS("error log of process_one_scraper", msg)
        raise CrawlInitError(500, "Unknown Error") from e


async def process_one_scraper(scraper: ScraperNameAndParams) -> str | None:
    return await run_with_crawl_error(
        crawler.process_one_scraper(scraper),
        scraper,
    )


running_lock = asyncio.Lock()


async def start_to_crawl_all():
    global running_lock
    if running_lock.locked():
        logger.info("is crawling now")
        return
    logger.info("***Start all scrapers***")
    async with running_lock:
        try:
            await crawler.process_scraper_groups(create_scraper_name_and_params(name) for name in Plugins.get_all_id())
        except CrawlError as e:
            if e.code in (400, 422, 500):
                raise  # 已知的错误就抑制
    logger.info("***Have finished all scrapers***")


if __name__ == "__main__":
    asyncio.run(start_to_crawl_all())
    # .env/bin/python -m src.crawler
