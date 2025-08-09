import re
from datetime import datetime
from typing import AsyncGenerator, Self

from bs4 import BeautifulSoup, Tag

from src.scraper.model import SortKey
from src.scraper.scraper import WebsiteScraper
from src.scraper.scraper_error import CreateButRequestFail, CreateByInvalidParam
from src.scraper.tools import AsyncBrowserManager, get_response_or_none


class MangaCopy(WebsiteScraper):
    home_url = "https://www.mangacopy.com"
    page_turning_duration = 10

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

    @classmethod
    async def create(cls, book_title: str, book_id: str) -> Self:
        """
        Args:
            book_title: 漫画名称。约束：不为空。
            book_id: 漫画在该网站下的 id ，可以在漫画主页的网址中拿到，如 https://www.mangacopy.com/comic/huaxoajiedexinfushenghuo 中最后一串。约束：不为空且由数字或字母组成。
        """
        if not (book_title and MangaCopy.is_valid_book_id(book_id)):
            raise CreateByInvalidParam()
        book_url = f"{cls.home_url}/comic/{book_id}"
        if await cls.book_exists(book_url):
            return cls(book_id, book_title, book_url)
        raise CreateButRequestFail()

    def __init__(self, *args) -> None:
        super().__init__()
        self.book_id, self.book_title, self.book_url = args

    def _source_info(self):
        return {
            "name": self.book_title,
            "link": self.book_url,
            "desc": f"拷貝漫畫里的漫画 —— {self.book_title}",
            "lang": "zh-CN",
            "key4sort": SortKey.CHAPTER_NUMBER,
            "table_name": f"mangacopy_book_{self.book_id}",
        }

    @classmethod
    async def _parse(cls, flags, book_title: str, book_url: str) -> AsyncGenerator[dict, None]:
        cls._logger.info("拷貝漫畫 start to parse")
        html_content = await AsyncBrowserManager.get_html_or_none(book_title, book_url, cls.headers["User-Agent"])
        if html_content is None:
            return

        soup = BeautifulSoup(html_content, features="lxml")
        articles = soup.find('div', id='default全部')
        if not articles or not isinstance(articles, Tag):
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
        image_link_tag = soup.find('img')
        if not image_link_tag or not isinstance(image_link_tag, Tag):
            image_link = "http://example.com"
        else:
            image_link = image_link_tag["src"]

        for num, a in reversed(articles_with_num):
            title = a["title"]
            article_url = f"{cls.home_url}{a['href']}"
            article = {
                "title": title,
                "summary": description,
                "link": article_url,
                "image_link": image_link,
                "chapter_number": num,
                "pub_time": time_obj
            }
            yield article

    def _custom_parameter_of_parse(self) -> list:
        return [self.book_title, self.book_url]

    @classmethod
    async def book_exists(cls, book_url: str):
        response = await get_response_or_none(book_url, cls.headers)
        return response and response.status_code == 200

    @staticmethod
    def is_valid_book_id(s: str) -> bool:
        return isinstance(s, str) and 0 < len(s) and all(c.isalnum() for c in s)
