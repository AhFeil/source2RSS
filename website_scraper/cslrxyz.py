import asyncio
from datetime import datetime

from typing import AsyncGenerator, Any

import httpx
from bs4 import BeautifulSoup


class CSLRXYZ:
    title = "二语习得英语学习中文网"
    home_url = "http://cslrxyz.xyz"
    # 请求每页之间的间隔，秒
    page_turning_duration = 10
    sort_by_key = "pub_time"

    # 数据库要有一个表或集合保存每个网站的元信息，生成 RSS 使用
    source_info = {
        "title": title,
        "link": home_url,
        "description": "分享英语学习方法、工具使用和影评",
        "language": "zh-CN"
    }

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Referer': 'http://cslrxyz.xyz/',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    }

    @classmethod
    async def parse(cls, start_page: int=1) -> AsyncGenerator[dict, Any]:
        """给起始页码，yield 一篇一篇惰性返回，直到最后一页最后一篇"""
        while True:
            url = f"http://cslrxyz.xyz/index.php/page/{start_page}/"

            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url=url, headers=cls.headers)

            soup = BeautifulSoup(response.text, features="lxml")
            all_articles = soup.find_all('article', class_='excerpt')
            
            if not all_articles:
                return
            
            # 遍历所有<article class="excerpt">元素
            for article in all_articles:
                h2 = article.find('h2')
                title = h2.text.strip()
                article_url = h2.a["href"]

                image_link = article.find('a', class_='focus').img["data-src"]
                note = article.find('p', class_='note').text.strip()
                
                meta = article.find('p', class_='meta')
                time = meta.time.text.strip()
                time_obj = datetime.strptime(time, "%Y-%m-%d")

                article = {
                    "article_name": title,
                    "summary": note,
                    "article_url": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj
                }

                yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)
    
    @classmethod
    async def article_newer_than(cls, datetime_):
        async for a in CSLRXYZ.parse():
            if a["pub_time"] > datetime_:
                yield a
            else:
                return

    async def first_add(self, amount: int = 10):
        """接口.第一次添加时，要调用的接口"""
        # 获取最新的 10 条，
        i = 0
        async for a in CSLRXYZ.parse():
            if i < amount:
                i += 1
                yield a
            else:
                return

    def get_source_info(self):
        """接口.返回元信息，主要用于 RSS"""
        return CSLRXYZ.source_info

    def get_table_name(self):
        """接口.返回表名或者collection名称，用于 RSS 文件的名称"""
        return CSLRXYZ.title
    
    async def get_new(self, datetime_):
        """接口.第一次添加时，要调用的接口"""
        async for a in self.article_newer_than(datetime_):
            yield a


import api._v1
api._v1.register(CSLRXYZ)


async def test():
    c = CSLRXYZ()
    async for a in c.first_add():
        print(a)


if __name__ == "__main__":
    asyncio.run(test())


