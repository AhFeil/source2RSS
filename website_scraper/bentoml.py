from urllib.parse import quote
import json
import time
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any

import httpx


class BentoMLBlog:
    home_url = "https://www.bentoml.com/blog"
    admin_url = "https://admin.bentoml.com"

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'DNT': '1',
        'Origin': 'https://www.bentoml.com',
        'Referer': 'https://www.bentoml.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
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
    
    @classmethod
    async def parse(cls, start_page: int=1) -> AsyncGenerator[dict, Any]:
        """给起始页码（实际不是页码因为是瀑布流，1 代表前 12 个），yield 一篇一篇惰性返回，直到最后一篇"""
        while True:
            varied_query_dict = {"pagination[page]": start_page}
            query = '&'.join(f"{key}={value}" for key, value in varied_query_dict.items()) + '&' + cls.steady_query
            encoded_query = quote(query, safe='[]=&')
            url = "https://admin.bentoml.com/api/blog-posts?" + encoded_query

            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url=url, headers=cls.headers)
            articles = response.json()

            if not articles["data"]:
                return

            for a in articles["data"]:
                id = a["id"]
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
                    "id": id,
                    "article_name": name,
                    "summary": description,
                    "article_url": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj
                }

                yield article

            start_page += 1
    
    @classmethod
    async def article_newer_than(cls, datetime_):
        async for a in BentoMLBlog.parse():
            if a["pub_time"] > datetime_:
                yield a
            else:
                return
        

async def test():
    async for a in BentoMLBlog.article_newer_than(datetime(2024, 4, 1, 13, 19, 4, 115000)):
        print(a)


if __name__ == "__main__":
    asyncio.run(test())


