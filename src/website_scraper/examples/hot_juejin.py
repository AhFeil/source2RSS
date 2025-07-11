import asyncio
from datetime import datetime
from typing import AsyncGenerator

from bs4 import BeautifulSoup

from src.website_scraper.model import SortKey
from src.website_scraper.scraper import WebsiteScraper
from src.website_scraper.tools import AsyncBrowserManager, get_response_or_none


# 逻辑有缺陷，目前是每次运行将热榜按照  排序，取最新的，不会缺少新写的上热榜，但是旧的上热榜会缺少
class HotJuejin(WebsiteScraper):
    home_url = "https://juejin.cn"
    admin_url = "https://api.juejin.cn/content_api/v1/content"
    page_turning_duration = 60

    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-platform': '"Windows"',
    }

    steady_query_dict = {
        "category_id": 1,
        "type": "hot"
    }
    steady_query = '&'.join(f"{key}={value}" for key, value in steady_query_dict.items())

    def _source_info(self):
        return {
            "name": "掘金热榜",
            "link": self.__class__.home_url,
            "desc": "掘金热榜",
            "lang": "zh-CN",
            "key4sort": SortKey.PUB_TIME}

    @property
    def max_wait_time(self):
        return HotJuejin.page_turning_duration * 60

    @classmethod
    async def _parse(cls, flags) -> AsyncGenerator[dict, None]:
        url = f"{cls.admin_url}/article_rank?{cls.steady_query}"
        cls._logger.info("掘金热榜 start to parse")
        response = await get_response_or_none(url, cls.headers)
        if response is None:
            return
        data = response.json()
        if data and not data["data"]:
            return

        # 首次全读，其他时候按照文章 id 排序，从大到小读
        articles: list = data["data"]
        if not isinstance(articles, list):
            return
        articles.sort(key=lambda x: x["content"]["content_id"], reverse=True)

        for a in articles:
            title = a["content"]["title"]
            content_id = a["content"]["content_id"]
            article_url = f"{cls.home_url}/post/{content_id}"

            html_content = await AsyncBrowserManager.get_html_or_none("HotJuejin", article_url, cls.headers["User-Agent"])
            if html_content is None:
                break
            soup = BeautifulSoup(html_content, features="lxml")

            meta_info = soup.find('div', class_='meta-box')
            if not meta_info:
                break
            time_sth = meta_info.find('time', class_="time")
            if not time_sth:
                break
            time = time_sth["datetime"]
            time_obj = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
            description = soup.find('div', class_='message')
            description = description.p.text if description else ""
            image_link = soup.find('img', class_='medium-zoom-image')
            image_link = image_link["src"] if image_link else "http://example.com"

            article = {
                "title": title,
                "summary": description,
                "link": article_url,
                "image_link": image_link,
                "pub_time": time_obj
            }

            yield article
            await asyncio.sleep(cls.page_turning_duration)
