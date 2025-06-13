from datetime import datetime
from itertools import islice
from typing import AsyncGenerator, Any

from bs4 import BeautifulSoup

from src.website_scraper.model import SortKey
from src.website_scraper.scraper import WebsiteScraper
from src.website_scraper.tools import AsyncBrowserManager, create_rp


class GatesNotes(WebsiteScraper):
    home_url = "https://www.gatesnotes.com/"
    page_turning_duration = 5

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'cache-control': 'max-age=0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
    }

    def _source_info(self):
        source_info = {
            "name": "GatesNotes",
            "link": self.__class__.home_url,
            "desc": "The Blog of Bill Gates",
            "lang": "en-US",
            "key4sort": SortKey.PUB_TIME
        }
        return source_info

    @classmethod
    async def _parse(cls, flags) -> AsyncGenerator[dict, Any]:
        """返回首页前几个封面文章"""
        latest_article_title = flags.get("article_title", "")
        reader_url = cls.home_url + "home/home-page-topic/reader"
        rp = await create_rp(cls.home_url + "robots.txt")
        if not rp.can_fetch("source2RSSbot", reader_url):
            cls._logger.info("GatesNotes can't be fetched")
            return

        cls._logger.info("GatesNotes start to parse")
        blocked = ["image", "font", "media"]
        def block_func(route): return route.abort() if route.request.resource_type in blocked else route.continue_()
        html_content = await AsyncBrowserManager.get_html_or_none("GatesNotes", reader_url, cls.headers["User-Agent"], block_func)
        if html_content is None:
            return

        soup = BeautifulSoup(html_content, features="lxml")
        articles_title = soup.find_all('h1', class_='ArtHeadline')
        articles_desc = soup.find_all('div', class_='ArtDesc GNDescCopy')
        articles_url = soup.find_all('div', class_='Arteyebrow')
        articles_times = soup.find_all('span', class_='ArtDateTime')
        date_strs = islice(articles_times, 0, None, 2)
        for title, description, url, date_str in zip(articles_title, articles_desc, articles_url, date_strs):
            if title.text == latest_article_title:
                return
            article = {
                "title": title.text,
                "summary": description.text,
                "link": reader_url + '/' + url["id"].split("/", 1)[-1],
                "pub_time": datetime.strptime(date_str.text, "on %A, %b %d, %Y")
            }
            yield article
