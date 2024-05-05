import re
import asyncio
from datetime import datetime

from typing import AsyncGenerator, Any

import httpx


class FanQie:
    title = "番茄免费小说"
    home_url = "https://fanqienovel.com"
    admin_url = "http://82.157.53.75:1180"
    sort_by_key = "chapter_number"
    # 请求每页之间的间隔，秒
    page_turning_duration = 2
    # 设置超时和重试次数
    timeout = httpx.Timeout(10.0)
    
    def __init__(self, title, book_id) -> None:
        self.book_id = book_id
        book_info_url = f"{FanQie.admin_url}/info?book_id={book_id}"
        # 数据库要有一个表或集合保存每个网站的元信息，生成 RSS 使用
        self.source_info = {
            "title": title,
            "link": FanQie.home_url + f"/page/{book_id}",
            "description": f"番茄免费小说 - {title} 的更新篇幅",
            "language": "zh-CN"
        }

    @classmethod
    async def parse(cls, book_id: str, old2new: bool=False, start_chapter: int=1) -> AsyncGenerator[dict, Any]:
        """从最新章节，yield 一篇一篇惰性返回，直到起始章节"""
        # 获得章节信息
        catalog_url = f"{cls.admin_url}/catalog?book_id={book_id}"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            client.timeout = FanQie.timeout
            response = await client.get(url=catalog_url)
        data_json = response.json()
        
        book_info_json = data_json['data']['data']['book_info']
        image_link = book_info_json["audio_thumb_uri"]
        author = book_info_json["author"]
        abstract = book_info_json["abstract"]
        book_id = book_info_json["book_id"]
        book_name = book_info_json["book_name"]
        create_time = book_info_json["create_time"]
        last_chapter_title = book_info_json["last_chapter_title"]
        source = book_info_json["source"]   # 番茄转载的小说，来源网站
        abstract = book_info_json["abstract"]
        book_info = {
            "image_link": image_link,
            "author": author,
            "abstract": abstract,
            "book_id": book_id,
            "book_name": book_name,
            "create_time": create_time
        }

        catalog_list = data_json['data']['data'].get('catalog_data') or data_json['data']['data'].get('item_data_list')

        if old2new:
            # 反向，就是从第一篇开始返回，也就是 catalog_list 的原本顺序
            pass
        else:
            catalog_list = reversed(catalog_list)
        for i, c in enumerate(catalog_list):
            # 从旧到最新篇，可以指定从哪一章开始。反过来，从新到旧，就不能指定
            if old2new and i < start_chapter:
                continue
            item_id = c["item_id"]
            content_url = f"{cls.admin_url}/content?item_id={item_id}"
            async with httpx.AsyncClient(follow_redirects=True) as client:
                client.timeout = FanQie.timeout
                try:
                    response = await client.get(url=content_url)
                except (httpx.ConnectTimeout, httpx.ReadTimeout):
                    await asyncio.sleep(60)
                    response = await client.get(url=content_url)
            article_info = response.json()

            a = article_info["data"]["data"]
            chapter_title = a["title"]
            content = a['content']

            novel_data = a['novel_data']
            volume_name = novel_data["volume_name"]
            next_item_id = novel_data['next_item_id']
            pre_item_id = novel_data['pre_item_id']
            # 旧到新，到没有下一章 item_id 停止
            if old2new and next_item_id == "":
                break
            # 新到旧，到没有上一章 item_id 停止
            if not old2new and pre_item_id == "":
                break
            create_time = novel_data["create_time"]
            # 删除时区部分，单独处理
            s_time, s_tz = create_time.rsplit("+", 1)
            # 转换时间部分
            time_obj = datetime.strptime(s_time, "%Y-%m-%dT%H:%M:%S")
            
            chapter = re.findall(pattern=r"第(.*?)章", string=chapter_title) or re.findall(pattern=r"^(.*?)、", string=chapter_title) or [0]
            chapter = chapter[0]
            chapter_number = int(chapter)
            # 从旧到最新篇，修正，如果中间夹杂着通知类的章节，用这个补偿
            if old2new and chapter_number < start_chapter:
                continue
            article = {
                "article_name": chapter_title,
                "chapter": chapter_title,
                "chapter_number": chapter_number,
                "summary": content,
                "article_url": f"{cls.home_url}/reader/{item_id}?enter_from=page",
                "image_link": "",
                "pub_time": time_obj
            }

            yield article

            await asyncio.sleep(cls.page_turning_duration)

    async def chapter_greater_than(self, chapter: int):
        """从新到旧，直到小于指定的 chapter"""
        async for a in FanQie.parse(self.book_id):
            if a["chapter_number"] > chapter:
                yield a
            else:
                return

    async def chapter_after(self, chapter: int):
        """从旧到新，从 chapter 开始返回，直到最新的，为下载全本小说而写"""
        async for a in FanQie.parse(self.book_id, old2new=True, start_chapter=chapter + 1):
            if a["chapter_number"] > chapter:
                yield a
            else:
                return

    async def first_add(self, amount: int = 10):
        """接口.第一次添加时，要调用的接口"""
        # 获取最新的 10 条，
        i = 0
        async for a in FanQie.parse(self.book_id):
            if i < amount:
                i += 1
                yield a
            else:
                return

    def get_source_info(self):
        """接口.返回元信息，主要用于 RSS"""
        return self.source_info

    def get_table_name(self):
        """接口.返回表名或者collection名称，用于 RSS 文件的名称"""
        return self.source_info["title"]
    
    async def get_new(self, chapter: int):
        """接口.第二次和之后，要调用的接口"""
        async for a in self.chapter_greater_than(chapter):
            yield a


import api._v1
api._v1.register_c(FanQie)


async def test():
    book = FanQie("我不是戏神", "7276384138653862966")
    async for a in book.get_new(590):
        print(a["article_name"], a["pub_time"], a["chapter_number"])

    # 转载的
    book = FanQie("系统炸了，我成了系统", "6995119385308302344")
    async for a in book.chapter_after(5):
        print(a["article_name"], a["pub_time"], a["chapter_number"])

if __name__ == "__main__":
    asyncio.run(test())


