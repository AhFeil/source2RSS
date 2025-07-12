from contextlib import suppress
from datetime import datetime
from typing import AsyncGenerator, Self

from playwright.async_api import TimeoutError

from configHandle import post2RSS
from src.scraper.model import SortKey
from src.scraper.scraper import WebsiteScraper
from src.scraper.scraper_error import (
    CreateButRequestFail,
    CreateByInvalidParam,
    FailtoGet,
)
from src.scraper.tools import AsyncBrowserManager


class BilibiliUp(WebsiteScraper):
    home_url = "https://space.bilibili.com"
    page_turning_duration = 60
    support_old2new = True

    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'cache-control': 'max-age=0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-platform': '"Windows"',
    }

    @classmethod
    async def create(cls, uid: str) -> Self:
        """
        Args:
            uid: B 站用户的 uid ，可以在其个人主页查看，如 27016853 。约束：至少 4 位最多 25 位，由 0 - 9 组成。
        """
        if not BilibiliUp.is_valid_uid(uid):
            raise CreateByInvalidParam()
        space_url = f"{cls.home_url}/{uid}/dynamic"
        j_res = await cls.get_response_json(uid, space_url) # todo 如果是因为超时，应该对外表现为没有更新
        if j_res and j_res.get("data"):
            up_name = j_res["data"]["items"][0]["modules"]["module_author"]["name"]
            return cls(up_name, space_url, j_res)
        raise CreateButRequestFail()

    def __init__(self, up_name, space_url, j_res) -> None:
        super().__init__()
        self.up_name = up_name
        self.space_url = space_url
        self.j_res = j_res

    def _source_info(self):
        name_and_desc = f"B站UP{self.up_name}的动态"
        return {
            "name": name_and_desc,
            "link": self.space_url,
            "desc": name_and_desc,
            "lang": "zh-CN",
            "key4sort": SortKey.PUB_TIME}

    @property
    def max_wait_time(self):
        return BilibiliUp.page_turning_duration

    @classmethod
    async def _parse(cls, flags, up_name, j_res) -> AsyncGenerator[dict, None]:
        cls._logger.info(f"B站UP{up_name}的动态 start to parse")
        async for a in cls._parse_inner(j_res, flags.get("pub_time")):
            yield a

    @classmethod
    async def _parse_old2new(cls, flags, up_name, j_res) -> AsyncGenerator[dict, None]:
        cls._logger.info(f"B站UP{up_name}的动态 start to parse from old to new")
        async for a in cls._parse_inner(j_res, flags[SortKey.PUB_TIME], True):
            yield a

    @classmethod
    async def _parse_inner(cls, j_res, pub_time: datetime | None, reverse: bool=False) -> AsyncGenerator[dict, None]:
        """当 pub_time 为 False 时，按照网站显示顺序，即从新往旧依次返回； pub_time 有值时，则先定位，从旧往新返回，若未定位到，则从最旧的开始返回"""
        modules: list[dict] = j_res["data"]["items"]
        if not modules:
            return
        if tag := modules[0]["modules"].get("module_tag"):
            if tag.get("text") == "置顶":
                modules.sort(key=lambda m : m["modules"]["module_author"]["pub_ts"], reverse=True)
        new_modules = modules if not reverse else \
                    WebsiteScraper._range_by_desc_of(modules, pub_time, lambda x, f : f < datetime.fromtimestamp(x["modules"]["module_author"]["pub_ts"]))

        for m in new_modules:
            a = m["modules"]["module_dynamic"]
            author = m["modules"]["module_author"]
            time_obj = datetime.fromtimestamp(author["pub_ts"])
            if a["major"] is None: # 对视频评论的话是空的
                continue
            content = a["desc"]["text"] if a.get("desc") else ""
            if attributes := a["major"].get("archive"):
                name = attributes["title"]
                summary = attributes["desc"]
                article_url = "https:" + attributes["jump_url"] # bvid = attributes["bvid"]
                image_link = attributes["cover"]
            elif attributes := a["major"].get("opus"):
                name = author["name"] + "的专栏文章"
                summary = attributes["summary"]["rich_text_nodes"][0]["orig_text"]
                article_url = "https:" + attributes["jump_url"]
                image = attributes.get("pics")
                image_link = image[0]["url"] if image else ""
            else:
                continue

            article = {
                "title": name,
                "summary": summary,
                "link": article_url,
                "image_link": image_link,
                "content": content,
                "pub_time": time_obj
            }
            yield article

    def _custom_parameter_of_parse(self) -> list:
        return [self.up_name, self.j_res]

    @classmethod
    async def get_response_json(cls, uid, space_url) -> dict:
        user_agent = cls.headers["User-Agent"]
        id = str(uid)
        j_res = [{}]
        blocked = ["image", "font", "media"]
        def block_func(route): return route.abort() if route.request.resource_type in blocked else route.continue_()
        async with AsyncBrowserManager(id, user_agent) as context:
            await context.route("**/*", block_func)
            page = await context.new_page()
            AsyncBrowserManager._logger.debug("create page for " + id)
            page.on("response", lambda response: cls.handle_response(response, j_res))
            try:
                await page.goto(space_url, timeout=60000, wait_until='networkidle')
            except TimeoutError:
                AsyncBrowserManager._logger.warning(f"Page navigation of {id} timed out")
            except Exception as e:
                msg = f"Page navigation of {id} Exception occured: {e}"
                AsyncBrowserManager._logger.warning(msg)
                await post2RSS("error log of BilibiliUp when get_response_json", msg)
                raise FailtoGet() from e
            finally:
                await page.close()
                AsyncBrowserManager._logger.debug("destroy page of " + id)
        return j_res[0]

    @classmethod
    async def handle_response(cls, response, j_res) -> None:
        if '/x/polymer/web-dynamic/v1/feed/space' in response.url:
            with suppress(Exception):
                j_res[0] = await response.json()

    @staticmethod
    def is_valid_uid(s: str) -> bool:
        return isinstance(s, str) and 4 <= len(s) <= 25 and all(c.isdigit() for c in s)
