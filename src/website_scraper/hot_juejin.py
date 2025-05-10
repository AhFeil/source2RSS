import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any

from bs4 import BeautifulSoup
from playwright._impl._errors import TimeoutError
from src.utils import environment
from .example import WebsiteScraper, AsyncBrowserManager


# 逻辑有缺陷，目前是每次运行将热榜按照  排序，取最新的，不会缺少新写的上热榜，但是旧的上热榜会缺少
class HotJuejin(WebsiteScraper):
    title = "掘金热榜"
    home_url = "https://juejin.cn"
    admin_url = "https://api.juejin.cn/content_api/v1/content"
    page_turning_duration = 60
    key4sort = "pub_time"

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
    
    @property
    def source_info(self):
        return {
            "title": self.__class__.title,
            "link": self.__class__.home_url,
            "description": "掘金热榜",
            "language": "zh-CN",
            "key4sort": self.__class__.key4sort}

    @property
    def max_wait_time(self):
        return HotJuejin.page_turning_duration * 60
    
    @classmethod
    async def parse(cls, logger, start_page: int=1) -> AsyncGenerator[dict, Any]:
        url = f"{cls.admin_url}/article_rank?{cls.steady_query}"
        logger.info(f"{cls.title} start to parse page 1")   # 只有一页
        response = await cls.request(url)
        articles = response.json()
        if articles and not articles["data"]:
            return
        
        # 首次全读，其他时候按照文章 id 排序，从大到小读
        articles : list = articles["data"]
        if not isinstance(articles, list):
            return
        if start_page != 2:
            articles.sort(key=lambda x: x["content"]["content_id"], reverse=True)

        user_agent = environment.get_user_agent(cls.home_url)
        async with AsyncBrowserManager(user_agent) as context:
            page = await context.new_page()

            for a in articles:
                title = a["content"]["title"]
                content_id = a["content"]["content_id"]
                article_url = f"{cls.home_url}/post/{content_id}"
                try:
                    await page.goto(article_url, timeout=180000, wait_until='networkidle')   # 单位是毫秒，共 3 分钟
                except TimeoutError as e:
                    logger.warning(f"Page navigation timed out: {e}")
                    continue

                html_content = await page.content()
                soup = BeautifulSoup(html_content, features="lxml")

                meta_info = soup.find('div', class_='meta-box')
                time = meta_info.find('time', class_="time")
                if time:
                    time = time["datetime"]
                else:
                    continue
                time_obj = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
                description = soup.find('div', class_='message')
                description = description.p.text if description else ""
                image_link = soup.find('img', class_='medium-zoom-image')
                image_link = image_link["src"] if image_link else "http://example.com"

                article = {
                    "article_name": title,
                    "summary": description,
                    "article_url": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj
                }

                yield article
                await asyncio.sleep(cls.page_turning_duration)
            await page.close()


import api._v1
api._v1.register(HotJuejin)


async def test():
    w = HotJuejin()
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
    # python -m website_scraper.hot_juejin


