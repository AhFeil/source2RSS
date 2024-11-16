import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any

from bs4 import BeautifulSoup
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
        response = await cls.request(cls.home_url)
        soup = BeautifulSoup(response.text, features="lxml")
        first_artc = soup.find('div', class_='heromodule_hero', 
                       attrs={'data-module-name': 'Homepage hero', 'data-module-type': 'single_hero_module'})
        url = first_artc.find('a', href=True)['href']
        image_link = first_artc.find('img', src=True)['src']
        title = first_artc.find('div', class_='heromodule_title').text
        description = first_artc.find('div', class_='heromodule_description').p.text
        date_str = first_artc.find('div', class_='heromodule_herobydate').text
        time_obj = datetime.strptime(date_str, "%B %d, %Y")
        article = {
            "article_name": title,
            "summary": description,
            "article_url": cls.home_url + url,
            "image_link": image_link,
            "pub_time": time_obj
        }
        yield article

        # 找到 4 个文章所在 div，遍历所有<div class="TGN_site_ArticleItem">元素
        four_articles = soup.find('div', class_='TGN_site_ArticleItems FourSquareTGN_site_ArticleItems', attrs={'data-module-name': 'Homepage recent articles', 'data-module-type': 'feature_module'}).find_all('div', class_="TGN_site_ArticleItem")
        for article in four_articles:
            url = cls.home_url + article.find('a', href=True)['href']
            image_link = article.find('img', src=True)['src']
            title = article.find('div', class_='TGN_site_ArticleItemtitle').text
            description = article.find('div', class_='TGN_site_ArticleItemdescription').p.text

            await asyncio.sleep(cls.page_turning_duration)
            response = await cls.request(url)
            article_soup = BeautifulSoup(response.text, features="lxml")
            date_str = article_soup.find('div', class_="article_top_dateline").text.strip()
            time_obj = datetime.strptime(date_str, "%B %d, %Y")

            article = {
                "article_name": title,
                "summary": description,
                "article_url": url,
                "image_link": image_link,
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

