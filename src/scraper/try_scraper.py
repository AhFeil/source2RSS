# ruff: noqa: T201
from datetime import datetime

from src.scraper.model import LocateInfo
from src.scraper.scraper import WebsiteScraper


async def have_a_try(scraper_class: type[WebsiteScraper], *args):
    s_ins = await scraper_class.create(*args)

    flag: LocateInfo = {"article_title": "", "pub_time": datetime.now(), "amount": 10}
    async for a in s_ins.get(flag):
        print(a["title"], a["link"], a["pub_time"])

    print("-" * 20)
    flag: LocateInfo = {"article_title": "", "pub_time": datetime(2025, 5, 20)}
    async for a in s_ins.get(flag):
        print(a["title"], a["link"], a["pub_time"])


if __name__ == '__main__':
    import asyncio
    from config_handle import config

    if config.http_proxy_url:
        import os

        os.environ["http_proxy"] = config.http_proxy_url
        os.environ["https_proxy"] = config.http_proxy_url

        print("set proxy:", config.http_proxy_url)

    from src.scraper.examples.cslrxyz import CSLRXYZ
    asyncio.run(have_a_try(CSLRXYZ))
    # .env/bin/python -m src.scraper.try_scraper
