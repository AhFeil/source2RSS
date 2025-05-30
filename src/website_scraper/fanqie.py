import re
import asyncio
from typing import AsyncGenerator, Any, Self

from .example import WebsiteScraper, FailtoGet, CreateByInvalidParam


class FanQie(WebsiteScraper):
    title = "番茄免费小说"
    home_url = "https://fanqienovel.com"
    admin_url = "http://82.157.53.75:1180"
    page_turning_duration = 2
    support_old2new = True
    key4sort = "chapter_number"

    @classmethod
    async def create(cls, book_title: str, book_id: str) -> Self:
        book_info_json, catalog_list = await cls.get_catalog(book_id)
        if book_info_json and catalog_list:
            return cls(book_title, book_id, book_info_json, catalog_list)
        raise CreateByInvalidParam

    def __init__(self, *args) -> None:
        super().__init__()
        self.book_title, self.book_id, self.book_info_json, self.catalog_list = args

    @classmethod
    async def get_catalog(cls, book_id: str) -> tuple[dict, list]:
        """获取章节信息"""
        catalog_url = f"{cls.admin_url}/catalog?book_id={book_id}"
        response = await cls._request(catalog_url)
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

        info = {
            "name": self.book_title,
            "link": FanQie.home_url + f"/page/{self.book_id}",
            "desc": f"番茄免费小说 - {self.book_id} 的更新篇章",
            "lang": "zh-CN",
            # "book_name": book_name,
            # "image_link": image_link,
            # "author": author,
            # "abstract": abstract,
            # "source": source,
            # "create_time": create_time,
            "key4sort": FanQie.key4sort
        }
        return info

    @classmethod
    async def _parse(cls, logger, catalog_list: list, start_chapter: int | bool=False) -> AsyncGenerator[dict, Any]:
        """默认从最新章节，yield 一篇一篇惰性返回，直到起始章节；也可将 old2new 为真，会从 start_chapter 返回到最新"""
        logger.info(f"{cls.title} start to parse page")
        if not start_chapter:   # catalog_list 的顺序是第一篇到最新篇
            catalog_list.reverse()
        last_chapter_order = -1
        n = 0
        timer = WebsiteScraper._get_time_obj(start_chapter == False, count=10000)
        for i, c in enumerate(catalog_list, start=1):
            if start_chapter and i < start_chapter:
                # 从旧到最新篇，可以指定从哪一章开始。从新到旧不能指定
                continue

            item_id = c["item_id"]
            content_url = f"{cls.admin_url}/content?item_id={item_id}"
            try:
                response = await cls._request(content_url)
            except FailtoGet:
                await asyncio.sleep(60)
                response = await cls._request(content_url)

            article_info = response.json()
            a = article_info["data"]["data"]
            chapter_title = a["title"]
            chapter_number = FanQie._get_chapter_number(chapter_title)
            if start_chapter and chapter_number < start_chapter:
                # 从旧到最新篇，修正，如果中间夹杂着通知类的章节，用这个补偿
                continue

            content = a['content']
            novel_data = a['novel_data']
            volume_name = novel_data["volume_name"]
            next_item_id = novel_data['next_item_id']
            pre_item_id = novel_data['pre_item_id']
            real_chapter_order = int(novel_data['real_chapter_order'])

            # 抓取时若有两篇新的，如先是 21 章，然后 20 章，则 n 是 0 和 -1，这样旧的时间就小；反过来先 20 再 21，则 n = 0， n = 1，满足
            n += 0 if last_chapter_order == -1 else real_chapter_order - last_chapter_order

            article = {
                "title": chapter_title,
                "summary": content[0:100],
                "link": f"{cls.home_url}/reader/{item_id}?enter_from=page",
                "image_link": "",
                "content": content,
                "pub_time": next(timer),
                "chapter_number": chapter_number,
            }

            yield article

            # 旧到新，到没有下一章 item_id 停止
            if start_chapter and next_item_id == "":
                break
            # 新到旧，到没有上一章 item_id 停止
            if not start_chapter and pre_item_id == "":
                break
            
            last_chapter_order = real_chapter_order
            await asyncio.sleep(cls.page_turning_duration)

    def _custom_parameter_of_parse(self) -> list:
        return [self.catalog_list]

    @staticmethod
    def _get_chapter_number(chapter_title):
        chapter = re.findall(pattern=r"第(.*?)章", string=chapter_title) or re.findall(pattern=r"^(.*?)、", string=chapter_title) or [0] # type: ignore
        return int(chapter[0])


async def test():
    book = await FanQie.create("我不是戏神", "7276384138653862966")
    async for a in book.first_add(3):
        print(a["title"], a["pub_time"], a["chapter_number"])
    print("----------")
    async for a in book._get_from_old2new({"chapter_number": 1338}):
        print(a["title"], a["pub_time"], a["chapter_number"])
    print("--------------------")

    # 转载的
    book = await FanQie.create("系统炸了，我成了系统", "6995119385308302344")
    async for a in book.first_add(3):
        print(a["title"], a["pub_time"], a["chapter_number"])
    print("--------------------")


if __name__ == "__main__":
    asyncio.run(test())
    # .env/bin/python -m src.website_scraper.fanqie
