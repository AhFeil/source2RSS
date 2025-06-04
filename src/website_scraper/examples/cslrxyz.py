import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any

from bs4 import BeautifulSoup
from src.website_scraper.scraper import WebsiteScraper
from src.website_scraper.tools import get_response_or_none


class CSLRXYZ(WebsiteScraper):
    title = "二语习得英语学习中文网"
    home_url = "http://cslrxyz.xyz"
    page_turning_duration = 10
    key4sort = "pub_time"

    headers = {
        'Accept-Language': 'zh-CN,en-US',
        'Referer': 'http://cslrxyz.xyz/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    }

    def _source_info(self):
        source_info = {
            "name": self.__class__.title,
            "link": self.__class__.home_url,
            "desc": "分享英语学习方法、工具使用和影评",
            "lang": "zh-CN",
            "key4sort": self.__class__.key4sort
        }
        return source_info

    @classmethod
    async def _parse(cls, flags) -> AsyncGenerator[dict, Any]:
        """给起始页码，yield 一篇一篇惰性返回，直到最后一页最后一篇"""
        start_page = 1
        while True:
            url = f"http://cslrxyz.xyz/index.php/page/{start_page}/"
            cls._logger.info(f"{cls.title} start to parse page {start_page}")
            response = await get_response_or_none(url, cls.headers)
            if response is None:
                return

            soup = BeautifulSoup(response.text, features="lxml")
            all_articles = soup.find_all('article', class_='excerpt')
            if not all_articles:
                return

            # 遍历所有<article class="excerpt">元素
            for article in all_articles:
                h2 = article.find('h2')
                title = h2.text.strip()
                article_url = h2.a["href"]

                image_link = article.find('a', class_='focus').img["data-src"]
                note = article.find('p', class_='note').text.strip()

                meta = article.find('p', class_='meta')
                time = meta.time.text.strip()
                time_obj = datetime.strptime(time, "%Y-%m-%d")

                article = {
                    "title": title,
                    "summary": note,
                    "link": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj
                }

                yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)
