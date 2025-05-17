import re
import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Any

import httpx
from .example import WebsiteScraper, FailtoGet


class FanQie(WebsiteScraper):
    title = "番茄免费小说"
    home_url = "https://fanqienovel.com"
    admin_url = "http://82.157.53.75:1180"
    page_turning_duration = 2
    key4sort = "chapter_number"
    headers = {}
    
    def __init__(self, book_title, book_id) -> None:
        super().__init__()
        self.book_id = book_id
        self.book_title = book_title
        self.book_info_json, self.catalog_list = FanQie.get_catalog(self.logger, book_id)

    @classmethod
    def get_catalog(cls, logger, book_id: str) -> tuple[dict]:
        """获取章节信息"""
        catalog_url = f"{cls.admin_url}/catalog?book_id={book_id}"
        logger.info(f"{cls.title} start to parse catalog")
        with httpx.Client() as client:
            try:
                response = client.get(url=catalog_url)
            except (httpx.ConnectTimeout, httpx.ReadTimeout):
                raise FailtoGet
        
        data_json = response.json()
        book_info_json = data_json['data']['data']['book_info']
        catalog_list = data_json['data']['data'].get('catalog_data') or data_json['data']['data'].get('item_data_list')
        return book_info_json, catalog_list
    
    @property
    def source_info(self):
        """数据库要有一个表或集合保存每个网站的元信息，生成 RSS 使用"""
        book_info_json = self.book_info_json
        image_link = book_info_json["audio_thumb_uri"]
        author = book_info_json["author"]
        abstract = book_info_json["abstract"]
        book_name = book_info_json["book_name"]
        create_time = book_info_json["create_time"]
        # 删除时区部分，单独处理
        # s_time, _ = create_time.rsplit("+", 1)
        # time_obj = datetime.strptime(s_time, "%Y-%m-%dT%H:%M:%S")
        last_chapter_title = book_info_json["last_chapter_title"]
        source = book_info_json["source"]   # 番茄转载的小说，来源网站
        abstract = book_info_json["abstract"]

        return {
            "title": self.book_title,
            "link": FanQie.home_url + f"/page/{self.book_id}",
            "description": f"番茄免费小说 - {self.book_id} 的更新篇章",
            "language": "zh-CN",
            "book_name": book_name,
            "image_link": image_link,
            "author": author,
            "abstract": abstract,
            "source": source,
            "create_time": create_time,
            "key4sort": FanQie.key4sort}

    @classmethod
    async def parse(cls, logger, catalog_list: list, old2new: bool=False, start_chapter: int=1) -> AsyncGenerator[dict, Any]:
        """默认从最新章节，yield 一篇一篇惰性返回，直到起始章节；也可将 old2new 为真，会从 start_chapter 返回到最新"""
        if old2new:
            # 反向，就是从第一篇开始返回，也就是 catalog_list 的原本顺序
            pass
        else:
            catalog_list = reversed(catalog_list)
        last_chapter_order = -1
        n = 0
        current_time = datetime.now()
        for i, c in enumerate(catalog_list, start=1):
            if old2new and i < start_chapter:
                # 从旧到最新篇，可以指定从哪一章开始。从新到旧不能指定
                continue

            item_id = c["item_id"]
            content_url = f"{cls.admin_url}/content?item_id={item_id}"
            logger.info(f"{cls.title} start to parse page {i}")
            try:
                response = await cls.request(content_url)
            except FailtoGet:
                await asyncio.sleep(60)
                response = await cls.request(content_url)
            
            article_info = response.json()
            a = article_info["data"]["data"]
            chapter_title = a["title"]
            content = a['content']

            novel_data = a['novel_data']
            volume_name = novel_data["volume_name"]
            next_item_id = novel_data['next_item_id']
            pre_item_id = novel_data['pre_item_id']
            real_chapter_order = int(novel_data['real_chapter_order'])
            
            chapter = re.findall(pattern=r"第(.*?)章", string=chapter_title) or re.findall(pattern=r"^(.*?)、", string=chapter_title) or [0]
            chapter_number = int(chapter[0])
            if old2new and chapter_number < start_chapter:
                # 从旧到最新篇，修正，如果中间夹杂着通知类的章节，用这个补偿
                continue

            # 抓取时若有两篇新的，如先是 21 章，然后 20 章，则 n 是 0 和 -1，这样旧的时间就小；反过来先 20 再 21，则 n = 0， n = 1，满足
            n += 0 if last_chapter_order == -1 else real_chapter_order - last_chapter_order
            amend_pub_time = current_time + timedelta(minutes=2 * n)

            article = {
                "article_name": chapter_title,
                "chapter": chapter_title,
                "chapter_number": chapter_number,
                "summary": content[0:100],
                "content": content,
                "article_url": f"{cls.home_url}/reader/{item_id}?enter_from=page",
                "image_link": "",
                "pub_time": amend_pub_time
            }

            yield article

            # 旧到新，到没有下一章 item_id 停止
            if old2new and next_item_id == "":
                break
            # 新到旧，到没有上一章 item_id 停止
            if not old2new and pre_item_id == "":
                break
            
            last_chapter_order = real_chapter_order
            await asyncio.sleep(cls.page_turning_duration)

    def custom_parameter_of_parse(self) -> list:
        return [self.catalog_list]

    async def chapter_after(self, chapter: int):
        """从旧到新，从 chapter 开始返回，直到最新的，为下载全本小说而写"""
        async for a in FanQie.parse(self.logger, self.catalog_list, old2new=True, start_chapter=chapter + 1):
            if a["chapter_number"] > chapter:
                yield a
            else:
                return


async def test():
    book = FanQie("我不是戏神", "7276384138653862966")
    print(book.source_info)
    print(book.table_name)
    async for a in book.first_add():
        print(a["article_name"], a["pub_time"], a["chapter_number"])
    print("----------")
    async for a in book.get_new(600):
        print(a["article_name"], a["pub_time"], a["chapter_number"])
    print("--------------------")

    # 转载的
    book = FanQie("系统炸了，我成了系统", "6995119385308302344")
    print(book.source_info)
    print(book.table_name)
    async for a in book.chapter_after(5):
        print(a["article_name"], a["pub_time"], a["chapter_number"])
        break
    print("--------------------")


if __name__ == "__main__":
    asyncio.run(test())
    # python -m website_scraper.fanqie
