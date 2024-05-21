import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any

from .example import WebsiteScraper, FailtoGet


class CNUDaily(WebsiteScraper):
    title = "CNU 每日精选"
    home_url = "http://www.cnu.cc/"
    page_turning_duration = 5
    sort_by_key = "pub_time"

    headers = {
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Referer': 'http://www.cnu.cc/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    @property
    def source_info(self):
        return {
            "title": self.__class__.title,
            "link": self.__class__.home_url,
            "description": "CNU 每日精选",
            "language": "zh-CN"}

    @classmethod
    async def parse(cls, logger, start_page: int=1) -> AsyncGenerator[dict, Any]:
        """按照从新到旧的顺序返回"""
        while True:
            url = f"http://www.cnu.cc/selectedsFlow/{start_page}"
            logger.info(f"{cls.title} start to parse page {start_page}")
            response = await cls.request(url)

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
                        "article_name": name,
                        "author_display_name": author_display_name,
                        "author_id": author_id,
                        "category": category,
                        "summary": "",
                        "content": description,
                        "article_url": article_url,
                        "image_link": image_link,
                        "pub_time": time_obj
                    }

                    yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)


import api._v1
api._v1.register(CNUDaily)


async def test():
    w = CNUDaily()
    print(w.source_info)
    print(w.table_name)
    async for a in w.first_add():
        print(a)
    print("----------")
    async for a in w.get_new(datetime(2024, 5, 1)):
        print(a)
    print("----------")


if __name__ == "__main__":
    asyncio.run(test())
    # python -m website_scraper.cnu_daily

