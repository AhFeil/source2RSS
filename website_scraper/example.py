from urllib.parse import quote
import asyncio
from datetime import datetime

from typing import AsyncGenerator, Any

import httpx


class WebsiteScraper:
    title = "技焉洲"
    home_url = "https://yanh.tech/"
    admin_url = "https://yanh.tech/wp-content"
    sort_by_key = "pub_time"
    # 请求每页之间的间隔，秒
    page_turning_duration = 5

    # 数据库要有一个表或集合保存每个网站的元信息，生成 RSS 使用
    source_info = {
        "title": title,
        "link": home_url,
        "description": "Linux，单片机，编程",
        "language": "zh-CN"
    }

    # https://curlconverter.com/
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'DNT': '1',
        'Origin': 'https://yanh.tech',
        'Referer': 'https://yanh.tech',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
        'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }

    steady_query_dict = {
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
            await asyncio.sleep(cls.page_turning_duration)
    
    @classmethod
    async def article_newer_than(cls, datetime_):
        async for a in WebsiteScraper.parse():
            if a["pub_time"] > datetime_:
                yield a
            else:
                return

    async def first_add(self, amount: int = 10):
        """接口.第一次添加时，要调用的接口"""
        # 获取最新的 10 条，
        i = 0
        async for a in WebsiteScraper.parse():
            if i < amount:
                i += 1
                yield a
            else:
                return

    def get_source_info(self):
        """接口.返回元信息，主要用于 RSS"""
        return WebsiteScraper.source_info

    def get_table_name(self):
        """接口.返回表名或者collection名称，用于 RSS 文件的名称"""
        return WebsiteScraper.title
    
    async def get_new(self, datetime_):
        """接口.第一次添加时，要调用的接口"""
        async for a in self.article_newer_than(datetime_):
            yield a


import api._v1
api._v1.register(WebsiteScraper)


async def test():
    async for a in WebsiteScraper.article_newer_than(datetime(2024, 4, 1)):
        print(a)
    # 判断结尾是否正常
    # async for a in WebsiteScraper.parse(20):
    #     print(a)

if __name__ == "__main__":
    asyncio.run(test())


