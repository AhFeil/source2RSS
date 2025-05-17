import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Any

from bs4 import BeautifulSoup
from .example import WebsiteScraper, AsyncBrowserManager


class Chiphell(WebsiteScraper):
    title = "Chiphell"
    home_url = "https://www.chiphell.com/"
    page_turning_duration = 10
    key4sort = "pub_time"

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0',
        'cache-control': 'max-age=0',
        'sec-ch-ua': '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-platform': '"Windows"',
    }

    @property
    def source_info(self):
        source_info = {
            "title": self.__class__.title,
            "link": self.__class__.home_url,
            "description": "一个数码硬件社区",
            "language": "zh-CN",
            "key4sort": self.__class__.key4sort
        }
        return source_info

    @classmethod
    async def parse(cls, logger, start_page: int=1) -> AsyncGenerator[dict, Any]:
        """给起始页码，yield 一篇一篇惰性返回，直到最后一页最后一篇"""
        logger.info(f"{cls.title} start to parse page")
        html_content = await AsyncBrowserManager.get_html_or_none(cls.title, cls.home_url, cls.headers["User-Agent"])
        if html_content is None:
            return

        soup = BeautifulSoup(html_content, features="lxml")
        test_room = soup.find('div', class_='chip_index_pingce cl')
        if not test_room:
            return
        if test_room.div.span.text.strip() != "最新文章":
            logger.warning(f"{cls.title} structure has changed")
            return

        articles = test_room.find('div', class_='acon cl')
        if not articles:
            return
        li_elements = articles.select('ul#threadulid li')

        for a in li_elements:
            image = a.select_one('a.tm01 img')['src']
            title = a.select_one('a.tm03').text.strip()
            summary = a.select_one('div.tm04').text.strip()
            article_url = a.select_one('a.tm03')['href']
            time = a.select_one('div.avimain2 span').text
            time_obj = datetime.strptime(time, "%Y/%m/%d") - timedelta(minutes=start_page)
            start_page += 1

            article = {
                "article_name": title,
                "summary": summary,
                "article_url": Chiphell.home_url + article_url,
                "image_link": image,
                "pub_time": time_obj
            }
            yield article


import api._v1
api._v1.register(Chiphell)


async def test():
    c = Chiphell()
    print(c.source_info)
    print(c.table_name)
    async for a in c.first_add():
        print(a)
    print("----------")
    async for a in c.get_new(datetime(2025, 2, 10)):
        print(a)
    print("----------")


if __name__ == "__main__":
    asyncio.run(test())
    # .env/bin/python -m src.website_scraper.chiphell
