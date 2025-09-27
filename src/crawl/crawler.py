import asyncio
import logging
import signal
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self

from pydantic_core import ValidationError

from preproc import Plugins, config, data
from src.scraper import AsyncBrowserManager, WebsiteScraper
from src.scraper.scraper_error import (
    CreateButRequestFail,
    CreateByInvalidParam,
    CreateByLackAgent,
    CreateByLocked,
    FailtoGet,
)

from .crawl_error import CrawlError, CrawlInitError, CrawlRepeatError, CrawlRunError
from .local_publish import goto_uniform_flow

logger = logging.getLogger("crawler")


@dataclass
class ScraperNameAndParams:
    name: str       # TODO 不能是列表
    init_params: list | tuple | str # 如果参数只有一个，则可以为 str，多个用列表按顺序容纳，没有参数则使用空列表
    amount: int
    interval: int

    @classmethod
    def create(cls, cls_name: str, init_params_es: Iterable | None=None, amount: int | None=None, i_am_remote: bool=False) -> tuple[Self, ...]:
        """如果没有传入初始化参数等，就从配置中去取"""
        if cls_name == "Remote":
            return ()
        amount = amount or config.get_amount(cls_name)
        interval = config.get_interval(cls_name)
        agent = config.get_prefer_agent(cls_name)
        # 如果未提供参数，就从配置中取
        init_params_es = init_params_es or config.get_params(cls_name)
        # TODO
        if agent == "self" or i_am_remote:
            return tuple(cls(cls_name, init_params, amount, interval) for init_params in init_params_es)
        else:
            scrapers = []
            agents = data.agents.get(cls_name)
            if not agents:
                return ()
            for init_params in init_params_es:
                if not init_params:
                    new_params = [agents, cls_name]
                elif isinstance(init_params, tuple | list):
                    new_params = [agents, cls_name, *init_params]
                else:
                    new_params = [agents, cls_name, init_params]
                scrapers.append(cls("Remote", new_params, amount, interval))
            return tuple(scrapers)

    def __hash__(self):
        if self.name == "Remote":
            return hash(tuple(self.init_params[1:]))
        params = self.init_params if isinstance(self.init_params, (str, tuple)) else tuple(self.init_params)
        return hash((self.name, params))

    def __eq__(self, other):
        if self.name == "Remote" and other.name == "Remote":
            return self.init_params[1:] == other.init_params[1:]
        return self.name == other.name and self.init_params == other.init_params

running_scrapers = set()

def print_running_scrapers(signum, frame):
    print(f"\n[INFO] 当前 running_scrapers: {running_scrapers}", file=sys.stderr)  # noqa: T201

# 绑定信号
signal.signal(signal.SIGUSR1, print_running_scrapers)

def has_scraper(scraper: ScraperNameAndParams) -> bool:
    if scraper.name == "Representative":
        return False
    return scraper in running_scrapers

def add_scraper(scraper: ScraperNameAndParams):
    if scraper.name == "Representative":
        return
    running_scrapers.add(scraper)

async def discard_scraper(scraper: ScraperNameAndParams):
    if scraper.name == "Representative":
        return
    await asyncio.sleep(config.refractory_period)
    running_scrapers.discard(scraper)

"""
对于单例抓取器，同一时间只能有一个在运行，因此有运行时的实例时，新请求引发异常
对于多实例抓取器，参数相同的情况同上，参数不同的可以有多个
对于 Remote ，规则同上
对于 Representative ，不限制
"""
async def get_instance(scraper: ScraperNameAndParams) -> WebsiteScraper | None:
    cls: type[WebsiteScraper] | None = Plugins.get_plugin_or_none(scraper.name)
    # 根本无法创建，返回 None
    if cls is None or (not scraper.init_params and cls.is_variety):
        return
    # 可以创建，但是重复：有另一个相同的在运行，引发异常
    if has_scraper(scraper):

        logger.info("repeat instance of %s", str(scraper))
        raise CrawlRepeatError(f"repeat instance of {scraper.name}")
    # 最终创建实例
    add_scraper(scraper) # 需要保证每一处调用该函数的地方都能正常移除
    try:
        if not scraper.init_params:
            instance = await cls.create()
        elif isinstance(scraper.init_params, tuple | list):
            instance = await cls.create(*scraper.init_params)
        else:
            instance = await cls.create(scraper.init_params)
    except Exception:
        # 如果创建失败，短时间内另一个也不一定能成功，因此依然等待
        asyncio.create_task(discard_scraper(scraper))
        raise
    return instance

async def _process_one_kind_of_class(scrapers: tuple[ScraperNameAndParams, ...]) -> list[str]:  # noqa: C901
    """创建实例然后走统一流程"""
    res = []
    for scraper in scrapers: # TODO 将单个的抽出
        try:
            instance = await get_instance(scraper)
            if instance is None:
                continue
        except TypeError:
            raise CrawlInitError(400, "The amount of parameters is incorrect")  # noqa: B904
        except CreateByLocked:
            raise CrawlInitError(423, "Server is busy")  # noqa: B904
        except CreateByInvalidParam:
            raise CrawlInitError(422, "Invalid parameters")  # noqa: B904
        except CreateByLackAgent:
            raise CrawlInitError(423, "Lack agent")  # noqa: B904
        except (CreateButRequestFail, FailtoGet): # todo 多次连续出现，则 post2RSS
            raise CrawlInitError(503, "Failed when crawling")  # noqa: B904
        except CrawlError:
            raise
        except Exception as e:
            msg = f"fail when query rss {scraper.name}: {e}"
            logger.exception(msg)
            await config.post2RSS("error log of _process_one_kind_of_class", msg)
            raise CrawlInitError(500, "Unknown Error") from e
        else:
            try:
                source_name = await goto_uniform_flow(data, instance, scraper.amount)
            except ValidationError:
                raise CrawlRunError(422, "Invalid source meta")  # noqa: B904
            except Exception as e:
                msg = f"fail when goto_uniform_flow of {scraper.name}, {scraper.init_params=}: {e}"
                logger.exception(msg)
                await config.post2RSS("error log of goto_uniform_flow", msg)
                raise CrawlRunError(500, "Unknown Error") from e
            else:
                res.append(source_name)
            finally:
                asyncio.create_task(discard_scraper(scraper))
                await instance.destroy() # TODO 不能保证一定会清理资源
        await asyncio.sleep(scraper.interval)
    return res


async def start_to_crawl(clses: Iterable[tuple[ScraperNameAndParams, ...]]) -> list[list[str]]:
    """根据类名获得相应的类，和它们的初始化参数，组装协程然后放入事件循环"""
    tasks = (_process_one_kind_of_class(scrapers) for scrapers in clses if scrapers)
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
            await start_to_crawl(ScraperNameAndParams.create(name) for name in Plugins.get_all_id())
        except CrawlError as e:
            if e.code in (400, 422, 500):
                raise # 已知的错误就抑制
    logger.info("***Have finished all scrapers***")


if __name__ == "__main__":
    asyncio.run(start_to_crawl_all())
    # .env/bin/python -m src.crawl.crawler
