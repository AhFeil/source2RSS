import re
from datetime import datetime
from typing import AsyncGenerator, Self

import feedparser
from bs4 import BeautifulSoup

from src.scraper.model import SortKey
from src.scraper.scraper import WebsiteScraper
from src.scraper.scraper_error import CreateButRequestFail, CreateByInvalidParam
from src.scraper.tools import get_response_or_none


class YoutubeChannel(WebsiteScraper):
    home_url = "https://www.youtube.com"
    page_turning_duration = 10

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0',
    }

    @classmethod
    async def create(cls, channel_id: str) -> Self:
        """
        Args:
            channel_id: 可以在频道主页的网址中拿到，如 https://www.youtube.com/@kurzgesagt 中最后一串 kurzgesagt 。约束：不为空且由数字或字母组成。
        """
        if not YoutubeChannel.is_valid_channel_id(channel_id):
            raise CreateByInvalidParam()
        feed_url = await cls.get_feed_url(channel_id)
        if feed_url:
            response = await get_response_or_none(feed_url, cls.headers)
            if response and response.status_code == 200:
                feed = feedparser.parse(response.text)
                return cls(channel_id, feed.feed.title, feed) # type: ignore
        raise CreateButRequestFail()

    def __init__(self, channel_id, channel_name, feed) -> None:
        super().__init__()
        self.channel_id, self.channel_name, self.feed = channel_id, channel_name, feed

    def _source_info(self):
        return {
            "name": self.channel_id,
            "link": f"{self.__class__.home_url}/@{self.channel_id}",
            "desc": "Youtube Channel" + self.channel_name,
            "lang": "en-US",
            "key4sort": SortKey.PUB_TIME
        }

    @classmethod
    async def _parse(cls, flags, channel_name, feed) -> AsyncGenerator[dict, None]:
        """给起始页码，yield 一篇一篇惰性返回，直到最后一页最后一篇"""
        cls._logger.info(f"{channel_name} start to parse")
        for entry in feed.entries:
            # 如果没有更新，提前返回，减少一次网络请求
            if entry.title == flags.get("article_title"):
                return

            res = await get_response_or_none(entry.link, cls.headers) # type: ignore
            if res is None or res.status_code != 200:
                return
            duration_seconds = int(cls.extract_duration(res.text)) // 1000
            duration_m, duration_s = divmod(duration_seconds, 60)
            d = f"video duration is {duration_m}:{duration_s}. "
            article = {
                "title": entry.title,
                "summary": d + entry.summary[0:50],
                "link": entry.link,
                "image_link": entry.media_thumbnail[0]['url'],
                "content": d + entry.summary,
                "pub_time": datetime.fromisoformat(entry.published).replace(tzinfo=None), # type: ignore
            }
            yield article

    def _custom_parameter_of_parse(self) -> list:
        return [self.channel_name, self.feed]

    # todo 缓存
    @classmethod
    async def get_feed_url(cls, channel_id) -> str:
        response = await get_response_or_none(f"{YoutubeChannel.home_url}/@{channel_id}", cls.headers)
        if response is None or response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.text, features="lxml")
        feed_url = soup.find('link', rel='alternate', type="application/rss+xml", title="RSS")
        return feed_url["href"] if feed_url else "" # type: ignore

    @classmethod
    def extract_duration(cls, html_content):
        # 匹配 "approxDurationMs": "1310120",
        match = re.search(r'"approxDurationMs":\s*"(\d+)"', html_content)
        return match.group(1) if match else "1000"

    @staticmethod
    def is_valid_channel_id(s: str) -> bool:
        return isinstance(s, str) and 0 < len(s) and all(c.isalnum() or c in "-_" for c in s)
