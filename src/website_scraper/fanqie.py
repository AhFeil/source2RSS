import re
from datetime import datetime
import asyncio
from typing import AsyncGenerator, Self

from .example import WebsiteScraper, CreateByInvalidParam
from .tools import get_response_or_none

class FanQie(WebsiteScraper):
    title = "番茄免费小说"
    home_url = "https://fanqienovel.com"
    page_turning_duration = 2
    key4sort = "chapter_number"

    @classmethod
    async def create(cls, book_id: str, ip_or_domain, port, book_title: str="") -> Self:
        admin_url = f"http://{ip_or_domain}:{port}"
        book_info_json, catalog_list = await cls._get_catalog(admin_url, book_id)
        if book_info_json and catalog_list:
            return cls(book_title, book_id, admin_url, book_info_json, catalog_list)
        raise CreateByInvalidParam

    def __init__(self, *args) -> None:
        super().__init__()
        self.book_title, self.book_id, self.admin_url, self.book_info_json, self.catalog_list = args

    def _source_info(self):
        """数据库要有一个表或集合保存每个网站的元信息，生成 RSS 使用"""
        book_info_json = self.book_info_json
        book_name = book_info_json["book_name"]
        return {
            "name": self.book_title if self.book_title else book_name,
            "link": FanQie.home_url + f"/page/{self.book_id}",
            "desc": book_info_json["abstract"],
            "lang": "zh-CN",
            "image_link": book_info_json["audio_thumb_uri"],
            "author": book_info_json["author"],
            "source": book_info_json["source"],   # 番茄转载的小说，来源网站
            "create_time": book_info_json["create_time"],
            "key4sort": FanQie.key4sort
        }

    @classmethod
    async def _parse(cls, flags, book_info_json, catalog_list: list, admin_url) -> AsyncGenerator[dict, None]:
        start_chapter = flags.get(cls.key4sort)
        cls._logger.info(f"{cls.title} start to parse")
        async for a in cls._parse_inner(book_info_json, catalog_list, admin_url, start_chapter):
            yield a

    @classmethod
    async def _parse_old2new(cls, flags, book_info_json, catalog_list: list, admin_url) -> AsyncGenerator[dict, None]:
        start_chapter = flags[cls.key4sort]
        cls._logger.info(f"{cls.title} start to parse from old to new")
        async for a in cls._parse_inner(book_info_json, catalog_list, admin_url, start_chapter, True):
            yield a

    @classmethod
    async def _parse_inner(cls, book_info_json, catalog_list: list, admin_url, start_chapter: int | None, reverse: bool=False) -> AsyncGenerator[dict, None]:
        """从最新章节，yield 一篇一篇惰性返回，直到起始章节"""
        if not reverse:   # catalog_list 的顺序是第一篇到最新篇
            if start_chapter is not None:
                last_chapter_number = FanQie._get_chapter_number(book_info_json["last_chapter_title"])
                if last_chapter_number <= start_chapter:
                    return
            catalog_list.reverse()
        elif start_chapter is None: # 旧到新的情况下，如果没有设置起始章节，从 1 开始
            start_chapter = 1
        timer = WebsiteScraper._get_time_obj(not reverse, count=10000, current_time=datetime.fromtimestamp(int(book_info_json["last_chapter_update_time"])))
        for c in catalog_list:
            if reverse:
                # 从旧到最新篇，可以指定从哪一章开始。从新到旧不能指定
                chapter_number = FanQie._get_chapter_number(c["catalog_title"])
                if chapter_number <= start_chapter: # type: ignore
                    continue

            item_id = c["item_id"]
            content_url = f"{admin_url}/content?item_id={item_id}"
            response = await get_response_or_none(content_url, cls.headers)
            if response is None:
                await asyncio.sleep(60) # 重试一次
                response = await get_response_or_none(content_url, cls.headers)
                if response is None:
                    return
            article_info = response.json()
            a = article_info["data"]["data"]
            chapter_title = a["title"]
            chapter_number = FanQie._get_chapter_number(chapter_title)
            content = a['content']
            novel_data = a['novel_data']
            volume_name = novel_data["volume_name"]
            next_item_id = novel_data['next_item_id']
            pre_item_id = novel_data['pre_item_id']

            article = {
                "title": chapter_title,
                "summary": content[0:100],
                "link": f"{cls.home_url}/reader/{item_id}?enter_from=page",
                "image_link": "",
                "content": content,
                "pub_time": next(timer),
                "volume_name": volume_name,
                "chapter_number": chapter_number,
            }

            yield article

            # 旧到新，到没有下一章 item_id 停止
            if reverse and next_item_id == "":
                break
            # 新到旧，到没有上一章 item_id 停止
            if not reverse and pre_item_id == "":
                break

            await asyncio.sleep(cls.page_turning_duration)

    def _custom_parameter_of_parse(self) -> list:
        return [self.book_info_json, self.catalog_list, self.admin_url]

    @classmethod
    async def _get_catalog(cls, admin_url, book_id: str) -> tuple[dict, list]:
        """获取章节信息"""
        catalog_url = f"{admin_url}/catalog?book_id={book_id}"
        response = await get_response_or_none(catalog_url, cls.headers)
        if response is None:
            return {}, []
        data_json = response.json()
        book_info_json = data_json['data']['data']['book_info']
        catalog_list = data_json['data']['data'].get('catalog_data') or data_json['data']['data'].get('item_data_list')
        return book_info_json, catalog_list

    @staticmethod
    def _get_chapter_number(chapter_title):
        chapter = re.findall(pattern=r"第(.*?)章", string=chapter_title) or re.findall(pattern=r"^(.*?)、", string=chapter_title) or [0] # type: ignore
        return int(chapter[0])
