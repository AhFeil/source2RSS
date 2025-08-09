from datetime import datetime
from typing import AsyncGenerator

from src.scraper.model import SortKey
from src.scraper.scraper import WebsiteScraper
from src.scraper.tools import get_response_or_none


# 逻辑有缺陷，目前是每次运行将热榜按照  排序，取最新的，不会缺少新写的上热榜，但是旧的上热榜会缺少
class HotBilibili(WebsiteScraper):
    home_url = "https://www.bilibili.com/"
    page_turning_duration = 60

    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'cache-control': 'max-age=0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-platform': '"Windows"',
    }

    def _source_info(self):
        return {
            "name": "B站热榜",
            "link": self.__class__.home_url,
            "desc": "B站热榜",
            "lang": "zh-CN",
            "key4sort": SortKey.PUB_TIME,
            "table_name": "hot_bilibili",
        }

    @property
    def max_wait_time(self):
        return HotBilibili.page_turning_duration * 10

    @classmethod
    async def _parse(cls, flags) -> AsyncGenerator[dict, None]:
        cls._logger.info("B站热榜 start to parse")
        async for a in cls._parse_inner(flags.get("pub_time")):
            yield a

    @classmethod
    async def _parse_old2new(cls, flags) -> AsyncGenerator[dict, None]:
        cls._logger.info("B站热榜 start to parse from old to new")
        async for a in cls._parse_inner(flags[SortKey.PUB_TIME], True):
            yield a

    @classmethod
    async def _parse_inner(cls, pub_time: datetime | None, reverse: bool=False) -> AsyncGenerator[dict, None]:
        url = "https://api.bilibili.com/x/web-interface/ranking/v2"
        response = await get_response_or_none(url, cls.headers)
        if response is None:
            return
        res = response.json()
        if res and res.get("data"):
            res["data"]["list"].sort(key=lambda x: x["ctime"], reverse=True)
            articles = res["data"]["list"] if not reverse else \
                        WebsiteScraper._range_by_desc_of(res["data"]["list"], pub_time, lambda a, f : f < datetime.fromtimestamp(a["ctime"]))
            for a in articles:
                time_obj = datetime.fromtimestamp(a["ctime"])
                title = a["title"]
                description = a["desc"]
                article_url = f"https://www.bilibili.com/video/{a['bvid']}"
                image_link = a["pic"]

                article = {
                    "title": title,
                    "summary": description,
                    "link": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj
                }

                yield article
