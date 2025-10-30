import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from urllib.parse import quote

from src.scraper.model import SortKey
from src.scraper.scraper import WebsiteScraper
from src.scraper.tools import get_response_or_none


class BentoMLBlog(WebsiteScraper):
    home_url = "https://www.bentoml.com/blog"
    admin_url = "https://admin.bentoml.com"
    page_turning_duration = 5

    headers = {
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json',
        'Origin': 'https://www.bentoml.com',
        'Referer': 'https://www.bentoml.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        'sec-ch-ua-platform': '"Windows"',
    }

    steady_query_dict = {
        "pagination[pageSize]": 12,
        "pagination[withCount]": "true",
        "sort[0]": "overrideCreatedAt:desc",
        "sort[1]": "createdAt:desc",
        "populate[0]": "name",
        "populate[1]": "slug",
        "populate[2]": "description",
        "populate[3]": "image",
        "publicationState": "live"
    }
    steady_query = '&'.join(f"{key}={value}" for key, value in steady_query_dict.items())

    def _source_info(self):
        info = {
            'name': "BentoML Blog",
            'link': self.__class__.home_url,
            'desc': "Dive into the transformative world of AI application development with us!"
            "From expert insights to innovative use cases, we bring you the latest in efficiently deploying AI at scale.",
            'lang': "En",
            'key4sort': SortKey.PUB_TIME
        }
        return info

    @classmethod
    async def _parse(cls, flags) -> AsyncGenerator[dict, None]:  # noqa: ARG003
        start_page = 1
        while True:
            varied_query_dict = {"pagination[page]": start_page}
            query = '&'.join(f"{key}={value}" for key, value in varied_query_dict.items()) + '&' + cls.steady_query
            encoded_query = quote(query, safe='[]=&')
            url = "https://admin.bentoml.com/api/blog-posts?" + encoded_query
            cls._logger.info("BentoML Blog start to parse page %d", start_page)
            response = await get_response_or_none(url, cls.headers)
            if response is None:
                return
            articles = response.json()
            if not articles["data"]:
                return

            for a in articles["data"]:
                id_ = a["id"]
                attributes = a["attributes"]
                name = attributes["name"]
                description = attributes["description"]
                slug = attributes["slug"]
                article_url = cls.home_url + '/' + slug
                image = attributes["image"]
                image_link = cls.admin_url + image["data"]["attributes"]["url"]
                create_time = image["data"]["attributes"]["createdAt"]
                time_obj = datetime.strptime(create_time, "%Y-%m-%dT%H:%M:%S.%fZ")

                article = {
                    "id": id_,
                    "title": name,
                    "summary": description,
                    "link": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj
                }

                yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)
