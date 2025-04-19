import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright._impl._errors import TimeoutError
from utils import environment
from .example import WebsiteScraper


class GatesNotes(WebsiteScraper):
    title = "GatesNotes"
    home_url = "https://www.gatesnotes.com/"
    page_turning_duration = 5
    key4sort = "pub_time"

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'cache-control': 'max-age=0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
    }

    @property
    def source_info(self):
        source_info = {
            "title": self.__class__.title,
            "link": self.__class__.home_url,
            "description": "The Blog of Bill Gates",
            "language": "en-US",
            "key4sort": self.__class__.key4sort
        }
        return source_info
        
    @classmethod
    async def parse(cls, logger, start_page: int=1) -> AsyncGenerator[dict, Any]:
        """返回首页前 5 个封面文章"""
        logger.info(f"{cls.title} start to parse page {start_page}")
        user_agent = environment.get_user_agent(cls.home_url)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1920, "height": 1080}, accept_downloads=True, user_agent=user_agent)
            page = await context.new_page()
            try:
                await page.goto(cls.home_url, timeout=180000, wait_until='networkidle')   # 单位是毫秒，共 3 分钟
            except TimeoutError as e:
                logger.warning(f"Page navigation timed out: {e}")
                return
            else:
                html_content = await page.content()
        soup = BeautifulSoup(html_content, features="lxml")
        # 找到 4 个文章所在 div，遍历所有<div class="TGN_site_ArticleItem">元素
        articles_title = soup.find_all('div', class_='articleHeadline')
        articles_desc = soup.find_all('div', class_='articleDesc')
        articles_url = soup.find_all('a', class_=lambda cls_: cls_ and cls_.startswith('articleLeftF'))
        articles_img = soup.find_all('video', class_=lambda cls_: cls_ and cls_.startswith('TabletOnly articleBackF'))
        articles_times = WebsiteScraper.get_time_obj()
        for title, description, url, image_link, time_obj in zip(articles_title, articles_desc, articles_url, articles_img, articles_times):
            article = {
                "article_name": title.text,
                "summary": description.text,
                "article_url": url["href"],
                "image_link": image_link["src"],
                "pub_time": time_obj
            }
            yield article


import api._v1
api._v1.register(GatesNotes)


async def test():
    c = GatesNotes()
    print(c.source_info)
    print(c.table_name)
    async for a in c.first_add():
        print(a)
    print("----------")
    async for a in c.get_new(datetime(2024, 4, 1)):
        print(a)
    print("----------")


if __name__ == "__main__":
    asyncio.run(test())
    # python -m website_scraper.gatesnotes
