import re
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright._impl._errors import TimeoutError
from utils import environment
from .example import WebsiteScraper


class MangaCopy(WebsiteScraper):
    title = "拷貝漫畫"
    home_url = "https://www.mangacopy.com"
    page_turning_duration = 10
    key4sort = "chapter_number"

    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'referer': 'https://www.mangacopy.com/comic/huaxoajiedexinfushenghuo',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
    }

    def __init__(self, book_title, book_id) -> None:
        super().__init__()
        self.book_id = book_id
        self.book_title = book_title

    @property
    def source_info(self):
        return {
            "title": self.book_title,
            "link": f"{self.__class__.home_url}/comic/{self.book_id}",
            "description": f"拷貝漫畫下的作品 —— {self.book_title}",
            "language": "zh-CN",
            "key4sort": self.__class__.key4sort}
    
    @classmethod
    async def parse(cls, logger, book_id: str) -> AsyncGenerator[dict, Any]:
        url = f"{cls.home_url}/comic/{book_id}"
        logger.info(f"{cls.title} start to parse page")   # 只有一页
        user_agent = environment.get_user_agent(cls.home_url)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1920, "height": 1080}, accept_downloads=True, user_agent=user_agent)
            page = await context.new_page()
            try:
                await page.goto(url, timeout=60000, wait_until='networkidle')   # 单位是毫秒，共 1 分钟
            except TimeoutError as e:
                logger.warning(f"Page navigation timed out: {e}")
                return

            html_content = await page.content()
            soup = BeautifulSoup(html_content, features="lxml")
            articles = soup.find('div', id='default全部')
            if not articles:
                return
            articles = articles.find_all('a', style=re.compile(r'display:\s*(block|none);'))
            articles_with_num = [(num, a) for num, a in enumerate(articles, start=1)]

            for li in soup.find_all('li'):
                t: str = li.text.strip()
                if t.startswith("最後更新："):
                    time_obj = datetime.strptime(t.split('\n', 2)[1], "%Y-%m-%d")
                    break

            description = soup.find('p', class_='intro')
            description = description.text if description else ""
            image_link = soup.find('img')
            image_link = image_link["src"] if image_link else "http://example.com"

            for num, a in reversed(articles_with_num):
                title = a["title"]
                article_url = f"{cls.home_url}{a['href']}"
                article = {
                    "article_name": title,
                    "summary": description,
                    "article_url": article_url,
                    "image_link": image_link,
                    "chapter_number": num,
                    "pub_time": time_obj
                }
                yield article

    def custom_parameter_of_parse(self) -> list:
        return [self.book_id]


import api._v1
api._v1.register_c(MangaCopy)


async def test():
    w = MangaCopy("花咲家的性福生活", "huaxoajiedexinfushenghuo")
    print(w.source_info)
    print(w.table_name)
    async for a in w.first_add():
        print(a)
    print("----------")
    async for a in w.get_new(40):
        print(a)
    print("----------")


if __name__ == "__main__":
    asyncio.run(test())
    # python -m website_scraper.mangacopy
