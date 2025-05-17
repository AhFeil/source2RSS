import logging
import asyncio
import signal
from itertools import chain

from src.website_scraper import FailtoGet, CreateByInvalidParam
from src.local_publish import goto_uniform_flow

logger = logging.getLogger("crawler")


async def one_website(data, cls):
    """对某个网站的文章进行更新"""
    instance = await cls.create()
    await goto_uniform_flow(data, instance)


async def chapter_mode(config, data, cls, init_params: list):
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
            logger.info(f"FailtoGet: 初始化多实例情况时网络出错")
        except FailtoGet:
            logger.info(f"FailtoGet: 初始化多实例情况时网络出错")
        else:
            if url := config.remote_pub_scraper.get(cls.__name__):
                # 指定了远程发布网址，则通过 source2RSS 生成 RSS
                from src.remote_publish import goto_remote_flow
                await goto_remote_flow(config, data, instance, url)
            else:
                await goto_uniform_flow(data, instance)


async def monitor_website(config, data, plugins):
    """控制总流程： 解析，整合，保存，生成 RSS"""
    logger.info("***Start all scrapers***")

    tasks = chain(
        (chapter_mode(config, data, cls, config.get_params(cls.__name__)) for cls in plugins["chapter_mode"]),
        (one_website(data, cls) for cls in plugins["static"])
    )
    await asyncio.gather(*tasks)

    logger.info("***Have finished all scrapers***")


async def start_to_crawl():
    from preprocess import config, data, plugins

    # 开发环境下，每次都把集合清空
    if not config.is_production:
        logger.info("Clear All Collections")
        data._clear_db()
    
    await monitor_website(config, data, plugins)


if __name__ == "__main__":
    def handler(sig, frame):
        # 退出前清理环境
        exit(0)
    signal.signal(signal.SIGINT, handler)

    asyncio.run(start_to_crawl())
    # .env/bin/python -m src.crawler
