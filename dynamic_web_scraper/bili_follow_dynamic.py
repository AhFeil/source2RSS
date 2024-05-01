import json
import time
from urllib.parse import quote, urlencode
import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Any, Callable, Dict, List, Optional, Tuple, Union

import httpx
from playwright.async_api import BrowserContext, BrowserType, Page, async_playwright

from .login import BilibiliSign
from utils import environment, image_

from preprocess import config


class DataFetchError(httpx.RequestError):
    """something error when fetch"""


class BiliFoDynamic:
    title = "bilibili following dynamic"
    index_url = "https://www.bilibili.com"
    # 请求每页之间的间隔，秒
    page_turning_duration = 5
    # 关注动态到底是关注的所有 UP 主的最老的动态，因此不可能遍历，要限制一下
    limit_page = datetime.now() - timedelta(days=7)

    # 数据库要有一个表或集合保存每个网站的元信息，生成 RSS 使用
    source_info = {
        "title": title,
        "link": index_url,
        "description": "B 站个人动态",
        "language": "zh-CN"
    }

    def __init__(self):
        self.user_agent = environment.get_user_agent()
        self.state_path = config.bili_context
    
    async def get_valid_client(self, context):
        # stealth.min.js is a js script to prevent the website from detecting the crawler.
        await context.add_init_script(path=environment.get_init_script())
        page = await context.new_page()
        api_client = await self.create_bilibili_client(await context.cookies(), page)

        # 首页
        await page.goto(self.index_url)
        await page.wait_for_timeout(500)
        await page.screenshot(path=f"{config.screenshot_root}/bili_index.png")
        if await api_client.not_available():
            # API 客户端不可用的话，就登录
            base64_qrcode_img = await self.get_login_qrcode(page)
            await page.screenshot(path=f"{config.screenshot_root}/bili_login.png")
            # 将 base64 转化为图片保存
            asyncio.get_running_loop().run_in_executor(None, image_.save_qrcode, base64_qrcode_img, config.image_root)
            
            print(f"Waiting for scan code login")
            flag = await self.check_login_state(context)
            print(f"登录状态 {flag}")
            if not flag:
                return
            
            await context.storage_state(path=self.state_path)
            # 登录后更新
            cookie_str, cookie_dict = environment.convert_cookies(await context.cookies())
            await api_client.update_cookies(cookie_str, cookie_dict)
        # 返回拥有登录后的 cookie
        return api_client

    async def article_newer_than(self, datetime_):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=self.state_path, viewport={"width": 1920, "height": 1080}, accept_downloads=True, user_agent=self.user_agent)
            api_client = await self.get_valid_client(context)
            async for a in BiliFoDynamic.parse(api_client):
                if a["pub_time"] > datetime_:
                    yield a
                else:
                    return

    @classmethod
    async def parse(cls, api_client, start_page: int=1) -> AsyncGenerator[dict, Any]:
        """给起始页码（实际不是页码因为是瀑布流，1 代表前 n 个），yield 一篇一篇惰性返回，直到最后一篇"""
        offset = None
        while True:
            data = await api_client.get_dynamic(start_page, offset)

            if not data["has_more"]:
                return

            modules = data["items"]
            offset = data["offset"]
            for m in modules:
                a = m["modules"]["module_dynamic"]
                author = m["modules"]["module_author"]
                create_time = author["pub_ts"]
                time_obj = datetime.fromtimestamp(create_time)
                if a["major"] is None:
                    # 对视频评论的话是空的
                    continue
                if attributes := a["major"].get("archive"):
                    aid = attributes["aid"]
                    bvid = attributes["bvid"]
                    name = attributes["title"]
                    description = attributes["desc"]
                    article_url = attributes["jump_url"].lstrip('/')
                    image_link = attributes["cover"]
                elif attributes := a["major"].get("opus"):
                    aid = "0000000000"
                    bvid = "BV"
                    name = author["name"] + "的专栏文章"
                    description = attributes["summary"]["rich_text_nodes"][0]["orig_text"]
                    article_url = attributes["jump_url"].lstrip('/')
                    image_link = attributes.get("pics", [{"url": "http://example.com"}])[0]["url"]
                else:
                    continue

                article = {
                    "aid": aid,
                    "bvid": bvid,
                    "article_name": name,
                    "summary": description,
                    "article_url": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj
                }

                yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)
    

    async def get_login_qrcode(self, page):
        # click login button
        login_button_ele = page.locator("xpath=//div[@class='right-entry__outside go-login-btn']//div")
        await login_button_ele.click()
        # find login qrcode
        qrcode_img_selector = "//div[@class='login-scan-box']//img"
        elements = await page.wait_for_selector(
            selector=qrcode_img_selector,
        )
        base64_qrcode_img = str(await elements.get_property("src"))
        return base64_qrcode_img


    async def check_login_state(self, context) -> bool:
        for _ in range(30):
            _, cookie_dict = environment.convert_cookies(await context.cookies())
            if cookie_dict.get("SESSDATA", "") or cookie_dict.get("DedeUserID"):
                return True
            time.sleep(1)
        return False


    async def create_bilibili_client(self, cookies, page):
        cookie_str, cookie_dict = environment.convert_cookies(cookies)
        headers = {"User-Agent": self.user_agent, "Cookie": cookie_str}
        bilibili_client_obj = BilibiliClient(headers=headers, cookie_dict=cookie_dict, page=page)
        return bilibili_client_obj


class BilibiliClient:
    headers = {
        "User-Agent": None,
        "Cookie": None,
        "Origin": "https://www.bilibili.com",
        "Referer": "https://www.bilibili.com",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    def __init__(self, headers: Dict[str, str], cookie_dict: Dict[str, str], page, proxies=None, timeout=10):
        self.proxies = proxies
        self.timeout = timeout
        self.headers = BilibiliClient.headers | headers
        self._host = "https://api.bilibili.com"
        self.cookie_dict = cookie_dict
        self.page = page

    async def request(self, method, url, **kwargs) -> Any:
        async with httpx.AsyncClient(proxies=self.proxies) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)
        data: Dict = response.json()
        if data.get("code") != 0:
            raise DataFetchError(data.get("message", "unkonw error"))
        else:
            return data.get("data", {})

    async def get(self, uri: str, params=None, enable_params_sign: bool= True) -> Dict:
        final_uri = uri
        if enable_params_sign:
            params = await self.pre_request_data(params)
        if isinstance(params, dict):
            final_uri = (f"{uri}?{urlencode(params)}")
        return await self.request(method="GET", url=f"{self._host}{final_uri}", headers=self.headers)

    async def not_available(self) -> bool:
        """get a note to check if login state is ok"""
        try:
            check_login_uri = "/x/web-interface/nav"
            response = await self.get(check_login_uri)
            return False if response.get("isLogin") else True
        except Exception as e:
            print(e)
            return True
        
    async def pre_request_data(self, req_data: Dict) -> Dict:
        """请求参数签名
        需要从 localStorage 拿 wbi_img_urls 这参数，值如下：
        https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png-https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png
        """
        if not req_data:
            return {}
        img_key, sub_key = await self.get_wbi_keys()
        return BilibiliSign(img_key, sub_key).sign(req_data)

    async def get_wbi_keys(self) -> Tuple[str, str]:
        """获取最新的 img_key 和 sub_key"""
        local_storage = await self.page.evaluate("() => window.localStorage")
        wbi_img_urls = local_storage.get("wbi_img_urls", "") or local_storage.get(
            "wbi_img_url") + "-" + local_storage.get("wbi_sub_url")
        if wbi_img_urls and "-" in wbi_img_urls:
            img_url, sub_url = wbi_img_urls.split("-")
        else:
            resp = await self.request(method="GET", url=self._host + "/x/web-interface/nav")
            img_url: str = resp['wbi_img']['img_url']
            sub_url: str = resp['wbi_img']['sub_url']
        img_key = img_url.rsplit('/', 1)[1].split('.')[0]
        sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
        return img_key, sub_key
        
    async def post(self, uri: str, data: dict) -> Dict:
        data = await self.pre_request_data(data)
        json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return await self.request(method="POST", url=f"{self._host}{uri}",
                                  data=json_str, headers=self.headers)


    async def update_cookies(self, cookie_str, cookie_dict):
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def get_dynamic(self, page: int = 1, offset: str=None):
        uri = "/x/polymer/web-dynamic/v1/feed/all"
        query = {
            "type": "all",
            "platform": "web",
            "page": page,
            "features": "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote"
        }
        if offset:
            query["offset"] = offset
        return await self.get(uri, query)

    async def get_video_info(self, aid: Union[int, None] = None, bvid: Union[str, None] = None) -> Dict:
        """
        Bilibli web video detail api, aid 和 bvid任选一个参数
        :param aid: 稿件avid
        :param bvid: 稿件bvid
        :return:
        """
        if not aid and not bvid:
            raise ValueError("请提供 aid 或 bvid 中的至少一个参数")

        uri = "/x/web-interface/view/detail"
        params = dict()
        if aid:
            params.update({"aid": aid})
        else:
            params.update({"bvid": bvid})
        return await self.get(uri, params, enable_params_sign=False)

    # async def get_video_comments(self,
    #                              video_id: str,
    #                              order_mode: CommentOrderType = CommentOrderType.DEFAULT,
    #                              next: int = 0
    #                              ) -> Dict:
    #     """get video comments
    #     :param video_id: 视频 ID
    #     :param order_mode: 排序方式
    #     :param next: 评论页选择
    #     :return:
    #     """
    #     uri = "/x/v2/reply/wbi/main"
    #     post_data = {
    #         "oid": video_id,
    #         "mode": order_mode.value,
    #         "type": 1,
    #         "ps": 20,
    #         "next": next
    #     }
    #     return await self.get(uri, post_data)

    # async def get_video_all_comments(self, video_id: str, crawl_interval: float = 1.0, is_fetch_sub_comments=False,
    #                                  callback: Optional[Callable] = None, ):
    #     """
    #     get video all comments include sub comments
    #     :param video_id:
    #     :param crawl_interval:
    #     :param is_fetch_sub_comments:
    #     :param callback:
    #     :return:
    #     """

    #     result = []
    #     is_end = False
    #     next_page =0
    #     while not is_end:
    #         comments_res = await self.get_video_comments(video_id, CommentOrderType.DEFAULT, next_page)
    #         curson_info: Dict = comments_res.get("cursor")
    #         comment_list: List[Dict] = comments_res.get("replies", [])
    #         is_end = curson_info.get("is_end")
    #         next_page = curson_info.get("next")
    #         if callback:  # 如果有回调函数，就执行回调函数
    #             await callback(video_id, comment_list)
    #         await asyncio.sleep(crawl_interval)
    #         if not is_fetch_sub_comments:
    #             result.extend(comment_list)
    #             continue
    #         # todo handle get sub comments
    #     return result



import api._v1
api._v1.register_d(BiliFoDynamic)


async def test():
    b = BiliFoDynamic()
    async for a in b.article_newer_than(datetime(2024, 4, 20)):
        print(a)
    

if __name__ == "__main__":
    asyncio.run(test())


