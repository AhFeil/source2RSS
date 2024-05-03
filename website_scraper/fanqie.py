import re
import asyncio
from datetime import datetime
from dateutil import parser

from typing import AsyncGenerator, Any

import httpx


class FanQie:
    title = "番茄免费小说"
    home_url = "https://fanqienovel.com"
    admin_url = "http://82.157.53.75:1180"
    # 请求每页之间的间隔，秒
    page_turning_duration = 2

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
    async def parse(cls, book_id: str) -> AsyncGenerator[dict, Any]:
        """从最新章节，yield 一篇一篇惰性返回，直到起始章节"""
        # 获得章节信息
        catalog_url = f"{cls.admin_url}/catalog?book_id={book_id}"
        async with httpx.AsyncClient(follow_redirects=True) as client:
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
        book_info = {
            "image_link": image_link,
            "author": author,
            "abstract": abstract,
            "book_id": book_id,
            "book_name": book_name,
            "create_time": create_time
        }
        catalog_list = data_json['data']['data']['catalog_data']

        for c in reversed(catalog_list):
            item_id = c["item_id"]
            content_url = f"{cls.admin_url}/content?item_id={item_id}"
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url=content_url)
            article_info = response.json()

            a = article_info["data"]["data"]
            chapter_title = a["title"]
            content = a['content']

            novel_data = a['novel_data']
            volume_name = novel_data["volume_name"]
            next_item_id = novel_data['next_item_id']
            pre_item_id = novel_data['pre_item_id']
            if next_item_id == "":
                pass
            if pre_item_id == "":
                break
            create_time = novel_data["create_time"]
            # 删除时区部分，单独处理
            s_time, s_tz = create_time.rsplit("+", 1)
            # 转换时间部分
            time_obj = datetime.strptime(s_time, "%Y-%m-%dT%H:%M:%S")
            
            chapter = re.findall(pattern=r"第(.*?)章", string=chapter_title)[0]
            chapter_number = int(chapter)
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
    
    async def article_newer_than(self, datetime_):
        """获取的数据中，日期像是作者上传时的，而不是发出来的"""
        async for a in FanQie.parse(self.book_id):
            if a["pub_time"] > datetime_:
                yield a
            else:
                return

    async def chapter_greater_than(self, chapter: int):
        """获取的数据中，日期像是作者上传时的，而不是发出来的"""
        async for a in FanQie.parse(self.book_id):
            if a["chapter_number"] > chapter:
                yield a
            else:
                return


    async def latest_chapter_for(self, amount: int = 10):
        """获取的数据中，日期像是作者上传时的，而不是发出来的"""
        i = 0
        async for a in FanQie.parse(self.book_id):
            if i < amount:
                i += 1
                yield a
            else:
                return
            
import api._v1
api._v1.register_c(FanQie)


async def test():
    book = FanQie("我不是戏神", "7276384138653862966")
    async for a in book.chapter_greater_than(590):
        print(a["article_name"], a["pub_time"], a["chapter_number"])

if __name__ == "__main__":
    asyncio.run(test())


