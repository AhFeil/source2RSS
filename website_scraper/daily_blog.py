from urllib.parse import quote
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any

from .example import WebsiteScraper


class DailyBlog(WebsiteScraper):
    title = "值得一读技术博客"
    home_url = "https://daily-blog.chlinlearn.top/blogs"
    page_turning_duration = 5
    key4sort = "pub_time"

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Referer': 'https://daily-blog.chlinlearn.top/blogs/1',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
        'sec-ch-ua-platform': '"Windows"',
    }
    
    @property
    def source_info(self):
        return {
            "title": self.__class__.title,
            "link": self.__class__.home_url,
            "description": "让时间回归阅读！每日分享高质量技术博客，为您在信息流中精选值得一读的技术博客。一起探索技术世界，发现那些值得一读的技术博客、技术文档、产品创意。",
            "language": "zh-CN",
            "key4sort": self.__class__.key4sort}

    @classmethod
    async def parse(cls, logger, start_page: int=1) -> AsyncGenerator[dict, Any]:
        while True:
            query_dict = {"type": "new", "pageNum": start_page, "pageSize": 20}
            query = '&'.join(f"{key}={value}" for key, value in query_dict.items())
            encoded_query = quote(query, safe='[]=&')
            url = "https://daily-blog.chlinlearn.top/api/daily-blog/getBlogs/new?" + encoded_query
            logger.info(f"{cls.title} start to parse page {start_page}")
            response = await cls.request(url)

            articles = response.json()
            for a in articles["rows"]:
                id = a["id"]
                article_url = a["url"]
                author = a["author"]
                name = a["title"]
                image_link = a["icon"]
                publishTime = a["publishTime"]
                time_obj = datetime.strptime(publishTime, "%Y-%m-%d")
                
                article = {
                    "id": id,
                    "article_name": name,
                    "summary": name,
                    "article_url": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj,
                    "author": author
                }

                yield article
                if id <= 5:
                    return
                
            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)


import api._v1
api._v1.register(DailyBlog)


async def test():
    w = DailyBlog()
    print(w.source_info)
    print(w.table_name)
    async for a in w.first_add():
        print(a)
    print("----------")
    async for a in w.get_new(datetime(2024, 7, 15)):
        print(a)
    print("----------")


if __name__ == "__main__":
    asyncio.run(test())
    # python -m website_scraper.daily_blog


