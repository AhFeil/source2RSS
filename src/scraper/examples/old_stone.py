import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime

from bs4 import BeautifulSoup

from src.scraper.model import AccessLevel, SortKey
from src.scraper.scraper import WebsiteScraper
from src.scraper.tools import get_response_or_none


class OldStone(WebsiteScraper):
    home_url = "https://blog.mahyang.uk"
    page_turning_duration = 10

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    }

    def _source_info(self):
        source_info = {
            "name": "Old Stone",
            "link": self.__class__.home_url,
            "desc": "博客 Old Stone",
            "lang": "zh-CN",
            "key4sort": SortKey.PUB_TIME,
            "access": AccessLevel.SHARED_USER,
        }
        return source_info

    @classmethod
    async def _parse(cls, flags) -> AsyncGenerator[dict, None]: # noqa: ARG003
        """给起始页码，yield 一篇一篇惰性返回，直到最后一页最后一篇"""
        start_page = 1
        while True:
            cls._logger.info("Old Stone start to parse page %d", start_page)
            page = "" if start_page == 1 else f"page/{start_page}/"
            response = await get_response_or_none(f"{OldStone.home_url}/{page}", cls.headers)
            if response is None:
                return
            soup = BeautifulSoup(response.text, features="lxml")
            all_articles = soup.find_all('article', class_='post-block')
            if not all_articles:
                return

            # 遍历所有<article class="excerpt">元素
            for a in all_articles:
                header = a.find('header', class_='post-header')
                h2 = header.find('h2', class_='post-title')
                title = h2.text.strip()
                article_url = h2.a["href"]

                meta = header.find('div', class_='post-meta')
                time = meta.span.time["datetime"]
                s_time, _ = time.rsplit("+", 1)
                time_obj = datetime.strptime(s_time, "%Y-%m-%dT%H:%M:%S")

                summary = a.find('div', class_='post-body').text.strip()
                article = {
                    "title": title,
                    "summary": summary,
                    "link": OldStone.home_url + article_url,
                    "image_link": "http://example.com",
                    "pub_time": time_obj
                }

                yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)
