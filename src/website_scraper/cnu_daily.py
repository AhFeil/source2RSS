import asyncio
from datetime import datetime
from typing import AsyncGenerator

from .example import WebsiteScraper, FailtoGet


class CNUDaily(WebsiteScraper):
    title = "CNU 每日精选"
    home_url = "http://www.cnu.cc/"
    page_turning_duration = 5
    key4sort = "pub_time"

    headers = {
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Referer': 'http://www.cnu.cc/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
    }

    def _source_info(self):
        return {
            "name": self.__class__.title,
            "link": self.__class__.home_url,
            "desc": "CNU 每日精选",
            "lang": "zh-CN",
            "key4sort": self.__class__.key4sort}

    @classmethod
    async def _parse(cls, logger, start_page: int=1) -> AsyncGenerator[dict, None]:
        """按照从新到旧的顺序返回"""
        while True:
            url = f"http://www.cnu.cc/selectedsFlow/{start_page}"
            logger.info(f"{cls.title} start to parse page {start_page}")
            response = await cls._request(url)

            json_res = response.json()
            # 超出结尾了
            if json_res["status"] == "empty":
                return
            if json_res["status"] != "success":
                raise FailtoGet

            for day in json_res["data"]:
                create_time = day["date"]
                time_obj = datetime.strptime(create_time, "%Y-%m-%d")
                for w in day["works"]:
                    id = w["id"]
                    name = w["title"]
                    author_display_name = w["author_display_name"]
                    author_id = w["author_id"]
                    category = w["category"]
                    description = w["body"]
                    article_url = cls.home_url + f'works/{id}'
                    image_link = "http://imgoss.cnu.cc/" + w["cover"] + "&x-oss-process=style/cover280"

                    article = {
                        "id": id,
                        "title": name,
                        "author_display_name": author_display_name,
                        "author_id": author_id,
                        "category": category,
                        "summary": "",
                        "link": article_url,
                        "image_link": image_link,
                        "pub_time": time_obj,
                        "content": description,
                    }

                    yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)
