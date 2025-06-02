from datetime import datetime
from typing import AsyncGenerator, Self

from .example import WebsiteScraper, CreateByInvalidParam, FailtoGet
from .tools import AsyncBrowserManager


class BilibiliUp(WebsiteScraper):
    title = "B站UP"
    home_url = "https://space.bilibili.com"
    page_turning_duration = 60
    support_old2new = True
    key4sort = "pub_time"

    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'cache-control': 'max-age=0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
        'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-platform': '"Windows"',
    }

    @classmethod
    async def create(cls, uid: int) -> Self:
        space_url = f"{cls.home_url}/{uid}/dynamic"
        j_res = await cls.get_response_json(uid, space_url)
        if j_res and j_res.get("data"):
            up_name = j_res["data"]["items"][0]["modules"]["module_author"]["name"]
            return cls(up_name, space_url, j_res)
        raise CreateByInvalidParam

    def __init__(self, up_name, space_url, j_res) -> None:
        super().__init__()
        self.up_name = up_name
        self.space_url = space_url
        self.j_res = j_res

    def _source_info(self):
        return {
            "name": self.__class__.title + self.up_name + "的动态",
            "link": self.space_url,
            "desc": self.__class__.title + self.up_name + "的动态",
            "lang": "zh-CN",
            "key4sort": self.__class__.key4sort}

    @property
    def max_wait_time(self):
        return BilibiliUp.page_turning_duration

    @classmethod
    async def _parse(cls, flags, up_name, j_res) -> AsyncGenerator[dict, None]:
        cls._logger.info(f"{cls.title}{up_name} start to parse")
        async for a in cls._parse_inner(j_res, flags.get("pub_time")):
            yield a

    @classmethod
    async def _parse_old2new(cls, flags, up_name, j_res) -> AsyncGenerator[dict, None]:
        cls._logger.info(f"{cls.title}{up_name} start to parse from old to new")
        async for a in cls._parse_inner(j_res, flags[cls.key4sort], True):
            yield a

    @classmethod
    async def _parse_inner(cls, j_res, pub_time: datetime | None, reverse: bool=False) -> AsyncGenerator[dict, None]:
        """当 pub_time 为 False 时，按照网站显示顺序，即从新往旧依次返回； pub_time 有值时，则先定位，从旧往新返回，若未定位到，则从最旧的开始返回"""
        modules: list[dict] = j_res["data"]["items"]
        if not modules:
            return
        if modules[0]["modules"]["module_tag"].get("text") == "置顶":
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
            AsyncBrowserManager._logger.info("create page for " + id)
            page.on("response", lambda response: cls.handle_response(response, j_res))
            try:
                await page.goto(space_url, timeout=60000, wait_until='networkidle')
            except TimeoutError:
                AsyncBrowserManager._logger.warning(f"Page navigation of {id} timed out")
            except Exception as e:
                AsyncBrowserManager._logger.warning(f"Page navigation of {id} Exception occured: {e}")
                raise FailtoGet
            finally:
                await page.close()
                AsyncBrowserManager._logger.info("destroy page of " + id)
        return j_res[0]

    @classmethod
    async def handle_response(cls, response, j_res) -> None:
        if '/x/polymer/web-dynamic/v1/feed/space' in response.url:
            try:
                j_res[0] = await response.json()
            except Exception:
                pass
