import logging
import asyncio
import signal
from itertools import chain

from src.website_scraper import FailtoGet, CreateByInvalidParam, AsyncBrowserManager
from src.local_publish import goto_uniform_flow

logger = logging.getLogger("crawler")


async def one_website(data, cls, amount: int):
    """对某个网站的文章进行更新"""
    instance = await cls.create()
    await goto_uniform_flow(data, instance, amount)


async def chapter_mode(config, data, cls, init_params: list, amount: int):
    """对多实例的抓取器，比如番茄的小说，B 站用户关注动态"""
    for params in init_params:
        try:
            if isinstance(params, dict) or isinstance(params, str):
                instance = await cls.create(params)
            elif isinstance(params, list):
                instance = await cls.create(*params)
            else:
                instance = await cls.create()
        except CreateByInvalidParam:
            logger.info("FailtoGet: 初始化多实例情况时网络出错")
        except FailtoGet:
            logger.info("FailtoGet: 初始化多实例情况时网络出错")
        else:
            if url := config.remote_pub_scraper.get(cls.__name__):
                # 指定了远程发布网址，则通过 source2RSS 生成 RSS
                from src.remote_publish import goto_remote_flow
                await goto_remote_flow(config, data, instance, url)
            else:
                await goto_uniform_flow(data, instance, amount)


async def monitor_website(config, data, plugins):
    """控制总流程： 解析，整合，保存，生成 RSS"""
    logger.info("***Start all scrapers***")

    tasks = chain(
        (chapter_mode(config, data, cls, config.get_params(cls.__name__), config.get_amount(cls.__name__)) for cls in plugins["chapter_mode"]),
        (one_website(data, cls, config.get_amount(cls.__name__)) for cls in plugins["static"])
    )
    await asyncio.gather(*tasks)

    await AsyncBrowserManager.delayed_operation("crawler", 1)
    logger.info("***Have finished all scrapers***")


async def start_to_crawl(cls_names: list[str]):
    from preprocess import config, data, Plugins
    plugins = {"static": [], "chapter_mode": []}
    for c in cls_names:
        cls = Plugins.get_plugin_or_none(c)
        if cls is None:
            continue
        if cls.is_variety:
            plugins["chapter_mode"].append(cls)
        else:
            plugins["static"].append(cls)
    await monitor_website(config, data, plugins)


async def start_to_crawl_all():
    from preprocess import config, data, plugins

    await monitor_website(config, data, plugins)


if __name__ == "__main__":
    def handler(sig, frame):
        # 退出前清理环境
        exit(0)
    signal.signal(signal.SIGINT, handler)

    asyncio.run(start_to_crawl_all())
    # .env/bin/python -m src.crawler
