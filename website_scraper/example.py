import logging
from urllib.parse import quote
import asyncio
from datetime import datetime
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any

import httpx


class FailtoGet(Exception):
    pass

class WebsiteScraper(ABC):
    title = "技焉洲"
    home_url = "https://yanh.tech/"
    admin_url = "https://yanh.tech/wp-content"
    # 请求每页之间的间隔，秒
    page_turning_duration = 5
    key4sort = "pub_time"

    # https://curlconverter.com/
    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Content-Type': 'application/json',
        'Origin': 'https://yanh.tech',
        'Referer': 'https://yanh.tech',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    }
    
    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    @abstractmethod
    def source_info(self):
        """数据库要有一个表或集合保存每个网站的元信息，生成 RSS 使用"""
        return {
            "title": self.__class__.title,
            "link": self.__class__.home_url,
            "description": "Linux，单片机，编程",
            "language": "zh-CN",
            "key4sort": self.__class__.key4sort}

    @property
    def table_name(self):
        """返回表名或者collection名称，以及用于 RSS 文件的名称"""
        return self.source_info["title"]

    @property
    def max_wait_time(self):
        """返回在本次执行中，从执行开始到结束占用最长时间，单位秒"""
        return self.__class__.page_turning_duration * 20
    
    @classmethod
    @abstractmethod
    async def parse(cls, logger, start_page: int=1) -> AsyncGenerator[dict, Any]:
        """按照从新到旧的顺序返回"""
        while True:
            varied_query_dict = {"pagination[page]": start_page}
            query = '&'.join(f"{key}={value}" for key, value in varied_query_dict.items())
            encoded_query = quote(query, safe='[]=&')
            url = "https://admin.bentoml.com/api/blog-posts?" + encoded_query
            logger.info(f"{cls.title} start to parse page {start_page}")
            # 若出现 FailtoGet，则由调度那里接收并跳过
            response = await cls.request(url)

            # 初次适配使用，保存网站数据
            # with open("for_test.html", 'w', encoding='utf-8') as f:
            #     f.write(response.text)
            # break
            # 初次适配使用，读取网站数据
            # with open("for_test.html", 'r', encoding='utf-8') as f:
            #     response_text = f.read()
            
            articles = response.json()
            # 超出结尾了
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
    async def request(cls, url: str) -> httpx.Response | None:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(url=url, headers=cls.headers)
            except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout):
                raise FailtoGet
        return response
    
    def custom_parameter_of_parse(self) -> list:
        """调用 parse 时，额外需要提供的参数"""
        return []

    async def first_add(self, amount: int = 10):
        """接口.第一次添加时用的，比如获取最新的 10 条"""
        async for a in self.__class__.parse(self.logger, *self.custom_parameter_of_parse()):
            if amount > 0:
                amount -= 1
                yield a
            else:
                return
    
    async def get_new(self, flag: datetime | int):
        """接口.第一次添加时，要调用的接口"""
        async for a in self.__class__.parse(self.logger, *self.custom_parameter_of_parse()):
            if a[self.__class__.key4sort] > flag:
                yield a
            else:
                return


# import api._v1
# api._v1.register(WebsiteScraper)


async def test():
    w = WebsiteScraper()
    print(w.source_info)
    print(w.table_name)
    async for a in w.first_add():
        print(a)
    print("----------")
    async for a in w.get_new(datetime(2024, 4, 1)):
        print(a)
    print("----------")


if __name__ == "__main__":
    asyncio.run(test())
    # python -m website_scraper.example

