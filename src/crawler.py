import logging
import asyncio
import signal
from typing import Iterable

from src.website_scraper import WebsiteScraper, FailtoGet, CreateByInvalidParam, AsyncBrowserManager
from src.local_publish import goto_uniform_flow

logger = logging.getLogger("crawler")


class CrawlInitError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


async def process_crawl_flow_of_one(data, cls: WebsiteScraper, init_params: Iterable, amount: int) -> list[str]:
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
        except CreateByInvalidParam:
            raise CrawlInitError(422, "Invalid parameters")
        except FailtoGet:
            raise CrawlInitError(500, "Failed when crawling")
        except Exception as e:
            logger.error(f"fail when query rss {cls.__name__}: {e}")
            raise CrawlInitError(500, "Unknown Error")
        else:
            # todo
            # if url := config.remote_pub_scraper.get(cls.__name__):
            #     # 指定了远程发布网址，则通过 source2RSS 生成 RSS
            #     from src.remote_publish import goto_remote_flow
            #     await goto_remote_flow(config, data, instance, url)
            # else:
            #     await goto_uniform_flow(data, instance, amount)
            source_file_name = await goto_uniform_flow(data, instance, amount)
            res.append(source_file_name)
    return res


async def monitor_website(config, data, plugins):
    """控制总流程： 解析，整合，保存，生成 RSS"""
    logger.info("***Start all scrapers***")

    tasks = (process_crawl_flow_of_one(data, cls, config.get_params(cls.__name__), config.get_amount(cls.__name__)) for cls in plugins)
    await asyncio.gather(*tasks)

    await AsyncBrowserManager.delayed_operation("crawler", 1)
    logger.info("***Have finished all scrapers***")


async def start_to_crawl(cls_names: Iterable[str]):
    from preprocess import config, data, Plugins
    plugins = [cls for c in cls_names if (cls := Plugins.get_plugin_or_none(c))]
    await monitor_website(config, data, plugins)


if __name__ == "__main__":
    from preprocess import Plugins
    def handler(sig, frame):
        # 退出前清理环境
        exit(0)
    signal.signal(signal.SIGINT, handler)

    asyncio.run(start_to_crawl(Plugins.get_all_id()))
    # .env/bin/python -m src.crawler
