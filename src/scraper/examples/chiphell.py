from datetime import datetime, timedelta
from typing import AsyncGenerator

from bs4 import BeautifulSoup

from src.scraper.model import SortKey
from src.scraper.scraper import WebsiteScraper
from src.scraper.tools import AsyncBrowserManager


class Chiphell(WebsiteScraper):
    home_url = "https://www.chiphell.com/"
    page_turning_duration = 10

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0',
        'cache-control': 'max-age=0',
        'sec-ch-ua': '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-platform': '"Windows"',
    }

    def _source_info(self):
        source_info = {
            "name": "Chiphell",
            "link": self.__class__.home_url,
            "desc": "一个数码硬件社区",
            "lang": "zh-CN",
            "key4sort": SortKey.PUB_TIME
        }
        return source_info

    @classmethod
    async def _parse(cls, flags) -> AsyncGenerator[dict, None]:
        """给起始页码，yield 一篇一篇惰性返回，直到最后一页最后一篇"""
        start_page = 1
        cls._logger.info("Chiphell start to parse")
        html_content = await AsyncBrowserManager.get_html_or_none("Chiphell", cls.home_url, cls.headers["User-Agent"])
        if html_content is None:
            return

        soup = BeautifulSoup(html_content, features="lxml")
        test_room = soup.find('div', class_='chip_index_pingce cl')
        if not test_room:
            return
        if test_room.div.span.text.strip() != "最新文章":
            cls._logger.warning("Chiphell structure has changed")
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
                "title": title,
                "summary": summary,
                "link": cls.home_url + article_url,
                "image_link": image,
                "pub_time": time_obj
            }
            yield article
