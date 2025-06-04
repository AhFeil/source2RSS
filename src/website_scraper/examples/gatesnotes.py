from typing import AsyncGenerator, Any

from bs4 import BeautifulSoup

from src.website_scraper.scraper import WebsiteScraper
from src.website_scraper.tools import AsyncBrowserManager
from src.utils import environment


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

    def _source_info(self):
        source_info = {
            "name": self.__class__.title,
            "link": self.__class__.home_url,
            "desc": "The Blog of Bill Gates",
            "lang": "en-US",
            "key4sort": self.__class__.key4sort
        }
        return source_info

    @classmethod
    async def _parse(cls, flags) -> AsyncGenerator[dict, Any]:
        """返回首页前几个封面文章"""
        cls._logger.info(f"{cls.title} start to parse")
        latest_article_title = flags.get("article_title", "")
        user_agent = environment.get_user_agent(cls.home_url)
        html_content = await AsyncBrowserManager.get_html_or_none(cls.title, cls.home_url, user_agent)
        if html_content is None:
            return

        soup = BeautifulSoup(html_content, features="lxml")
        # 找到 4 个文章所在 div，遍历所有<div class="TGN_site_ArticleItem">元素
        articles_title = soup.find_all('div', class_='articleHeadline')
        articles_desc = soup.find_all('div', class_='articleDesc')
        articles_url = soup.find_all('a', class_=lambda cls_: cls_ and cls_.startswith('articleLeftF'))
        articles_img = soup.find_all('video', class_=lambda cls_: cls_ and cls_.startswith('TabletOnly articleBackF'))
        articles_times = WebsiteScraper._get_time_obj(True)
        for title, description, url, image_link, time_obj in zip(articles_title, articles_desc, articles_url, articles_img, articles_times):
            if title.text == latest_article_title:
                return
            article = {
                "title": title.text,
                "summary": description.text,
                "link": url["href"],
                "image_link": image_link["src"],
                "pub_time": time_obj
            }
            yield article
