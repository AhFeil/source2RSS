from datetime import datetime
from typing import AsyncGenerator, Self

from bs4 import BeautifulSoup
import feedparser
from src.website_scraper.scraper import WebsiteScraper, CreateByInvalidParam
from src.website_scraper.tools import get_response_or_none


class YoutubeChannel(WebsiteScraper):
    title = "Youtube Channel"
    home_url = "https://www.youtube.com"
    page_turning_duration = 10
    key4sort = "pub_time"

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0',
    }

    @classmethod
    async def create(cls, channel_name: str) -> Self:
        feed_url = await cls.get_feed_url(channel_name)
        if feed_url:
            return cls(channel_name, feed_url)
        raise CreateByInvalidParam

    def __init__(self, channel_name, feed_url) -> None:
        super().__init__()
        self.channel_name = channel_name
        self.feed_url = feed_url

    def _source_info(self):
        source_info = {
            "name": self.channel_name,
            "link": f"{self.__class__.home_url}/@{self.channel_name}",
            "desc": "Youtube Channel" + self.channel_name,
            "lang": "en-US",
            "key4sort": self.__class__.key4sort
        }
        return source_info

    @classmethod
    async def _parse(cls, flags, channel_name, feed_url) -> AsyncGenerator[dict, None]:
        """给起始页码，yield 一篇一篇惰性返回，直到最后一页最后一篇"""
        cls._logger.info(f"{channel_name} start to parse")
        response = await get_response_or_none(feed_url, cls.headers)
        if response is None or response.status_code != 200:
            return
        feed = feedparser.parse(response.text)   # feed.feed.title 频道名称
        for entry in feed.entries:
            article = {
                "title": entry.title,
                "summary": entry.summary[0:50],
                "link": entry.link,
                "image_link": entry.media_thumbnail[0]['url'],
                "content": entry.summary,
                "pub_time": datetime.fromisoformat(entry.published).replace(tzinfo=None), # type: ignore
            }
            yield article

    def _custom_parameter_of_parse(self) -> list:
        return [self.channel_name, self.feed_url]

    @classmethod
    async def get_feed_url(cls, channel_name) -> str:
        response = await get_response_or_none(f"{YoutubeChannel.home_url}/@{channel_name}", cls.headers)
        if response is None or response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.text, features="lxml")
        feed_url = soup.find('link', rel='alternate', type="application/rss+xml", title="RSS")
        return feed_url["href"] if feed_url else "" # type: ignore
