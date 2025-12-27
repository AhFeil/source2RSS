import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime

from bs4 import BeautifulSoup

from src.scraper.model import SortKey
from src.scraper.scraper import WebsiteScraper
from src.scraper.tools import get_response_or_none


class DotComPress(WebsiteScraper):
    home_url = "https://www.dotcom.press"
    page_turning_duration = 5
    table_name_formation = "dotcompress"

    headers = {
        'Accept-Language': 'en-US,en;q=0.9',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }

    def _source_info(self):
        source_info = {
            "name": "DotCom Press",
            "link": self.__class__.home_url,
            "desc": "Publishing for the internet age. Past emails from the Dot Com Press mailing list.",
            "lang": "en-US",
            "key4sort": SortKey.PUB_TIME,
            "table_name": "dotcompress",
        }
        return source_info

    @classmethod
    async def _parse(cls, flags) -> AsyncGenerator[dict, None]:
        url = f"{cls.home_url}/archive"
        cls._logger.info("Fetching %s", url)
        response = await get_response_or_none(url, cls.headers)
        if response is None:
            cls._logger.error("Failed to fetch %s", url)
            return

        soup = BeautifulSoup(response.text, features="lxml")
        article_list = soup.find('ul', class_='archive_ul__wRoJW')
        if not article_list:
            cls._logger.warning("No article list found")
            return

        for li in article_list.find_all('li', class_='archive_li__TBXlr'):
            link_tag = li.find('a')
            if not link_tag:
                continue

            title_tag = link_tag.find('h2')
            summary_tag = link_tag.find('p')
            time_tag = link_tag.find('time')

            if not time_tag:
                continue

            article_url = cls.home_url + link_tag.get('href', '') # type: ignore

            # Parse ISO datetime format like "2025-12-15T00:00:00.000Z"
            datetime_str = time_tag.get('datetime', '')
            pub_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00')) # type: ignore

            article = {
                "title": title_tag.text.strip() if title_tag else "",
                "summary": summary_tag.text.strip() if summary_tag else "",
                "link": article_url,
                "pub_time": pub_time
            }

            yield article

        await asyncio.sleep(cls.page_turning_duration)
