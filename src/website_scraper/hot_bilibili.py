import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any

from .example import WebsiteScraper


# 逻辑有缺陷，目前是每次运行将热榜按照  排序，取最新的，不会缺少新写的上热榜，但是旧的上热榜会缺少
class HotBilibili(WebsiteScraper):
    title = "B站热榜"
    home_url = "https://www.bilibili.com/"
    page_turning_duration = 60
    key4sort = "pub_time"

    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'cache-control': 'max-age=0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-platform': '"Windows"',
    }

    @property
    def source_info(self):
        return {
            "title": self.__class__.title,
            "link": self.__class__.home_url,
            "description": "B站热榜",
            "language": "zh-CN",
            "key4sort": self.__class__.key4sort}

    @property
    def max_wait_time(self):
        return HotBilibili.page_turning_duration * 10
    
    @classmethod
    async def parse(cls, logger, start_page: int=1) -> AsyncGenerator[dict, Any]:
        if start_page != 1:
            return
        url = "https://api.bilibili.com/x/web-interface/ranking/v2"
        logger.info(f"{cls.title} start to parse page 1")   # 只有一页
        response = await cls.request(url)
        articles = response.json()
        if articles and not articles["data"]:
            return
        
        # 按照文章 ctime 排序，从大到小读
        articles: list[dict] = articles["data"]["list"]
        articles.sort(key=lambda x: x["ctime"], reverse=True)

        for a in articles:
            title = a["title"]
            description = a["desc"]
            article_url = f"https://www.bilibili.com/video/{a['bvid']}"
            image_link = a["pic"]
            time_obj = datetime.fromtimestamp(a["ctime"])

            article = {
                "article_name": title,
                "summary": description,
                "article_url": article_url,
                "image_link": image_link,
                "pub_time": time_obj
            }

            yield article


async def test():
    w = HotBilibili()
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
    # python -m website_scraper.hot_bilibili


