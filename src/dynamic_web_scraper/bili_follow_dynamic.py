import time
from urllib.parse import urlencode
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Any

import httpx
from playwright.async_api import BrowserContext, async_playwright
from playwright._impl._errors import TimeoutError as pw_TimeoutError

# from .login import BilibiliSign
from utils import environment, image_
from website_scraper.example import WebsiteScraper, FailtoGet


class BiliFoDynamic(WebsiteScraper):
    title = "bilibili following dynamic"
    home_url = "https://www.bilibili.com"
    page_turning_duration = 5
    key4sort = "pub_time"

    def __init__(self, config_dict):
        super().__init__()
        self.config_dict = config_dict
        self.state_path = config_dict["bili_context"]
        self.screenshot_root = config_dict["screenshot_root"]
        self.image_root = config_dict["image_root"]
        # 数据库要有一个表或集合保存每个网站的元信息，生成 RSS 使用
        self.user_agent = environment.get_user_agent(config_dict['user_name'])

    def _source_info(self):
        """数据库要有一个表或集合保存每个网站的元信息，生成 RSS 使用"""
        return {
            "title": f"{self.config_dict['user_name']} 的关注动态",
            "link": self.__class__.home_url,
            "desc": f"{self.config_dict['user_name']} 的关注动态",
            "lang": "zh-CN",
            "key4sort": self.__class__.key4sort}

    async def get_valid_client(self, context: BrowserContext):
        # stealth.min.js is a js script to prevent the website from detecting the crawler.
        await context.add_init_script(path=environment.get_init_script())
        page = await context.new_page()
        api_client = BiliFoDynamic.create_bilibili_client(self.user_agent, await context.cookies())

        # 首页
        try:   # 进入首页都超时的话，就直接返回空，这次不再爬取
            await page.goto(self.home_url, timeout=60000)
            await page.wait_for_timeout(500)
            await page.screenshot(path=f"{self.screenshot_root}/bili_index.png")
        except pw_TimeoutError:
            raise FailtoGet
        
        if await api_client.not_available():
            # API 客户端不可用的话，就登录
            base64_qrcode_img = await self.get_login_qrcode(page)
            await page.screenshot(path=f"{self.screenshot_root}/bili_login.png")
            # 将 base64 转化为图片保存
            asyncio.get_running_loop().run_in_executor(None, image_.save_qrcode, base64_qrcode_img, self.image_root)
            
            self.logger.warning("Waiting for scan code login")
            for _ in range(60):
                if await api_client.not_available():
                    time.sleep(3)
                    cookie_str, cookie_dict = environment.convert_cookies(await context.cookies())
                    api_client.update_cookies(cookie_str, cookie_dict)
                else:
                    break
            else:
                self.logger.info("登录状态 False")
                raise FailtoGet
            
            await context.storage_state(path=self.state_path)

        # 返回拥有登录后的 cookie
        return api_client

    async def article_newer_than(self, datetime_, amount=None):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=self.state_path, viewport={"width": 1920, "height": 1080}, accept_downloads=True, user_agent=self.user_agent)
            api_client = await self.get_valid_client(context)
            self.logger.info("Successfully get a valid bilibilli client")

            if amount:
                async for a in BiliFoDynamic.parse(self.logger, api_client):
                    if amount > 0:
                        amount -= 1
                        yield a
                    else:
                        return
            else:
                async for a in BiliFoDynamic.parse(self.logger, api_client):
                    if a["pub_time"] > datetime_:
                        yield a
                    else:
                        return

    async def first_add(self, amount: int = 10):
        """接口.第一次添加时，要调用的接口"""
        # 获取最新的 10 条，
        async for a in self.article_newer_than(None, amount):
            yield a
    
    async def get_new(self, datetime_):
        """接口.第一次添加时，要调用的接口"""
        async for a in self.article_newer_than(datetime_):
            yield a
    
    @classmethod
    async def parse(cls, logger, api_client, start_page: int=1) -> AsyncGenerator[dict, Any]:
        offset = None
        while True:
            try:
                logger.info(f"{cls.title} start to parse page {start_page}")
                data = await api_client.get_dynamic(start_page, offset)
            except httpx.ConnectTimeout:
                raise FailtoGet

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
                    name = attributes["title"] + " - " + author["name"]
                    description = attributes["desc"]
                    article_url = "https:" + attributes["jump_url"]
                    image_link = attributes["cover"]
                elif attributes := a["major"].get("opus"):
                    aid = "0000000000"
                    bvid = "BV"
                    name = author["name"] + "的专栏文章"
                    description = attributes["summary"]["rich_text_nodes"][0]["orig_text"]
                    article_url = "https:" + attributes["jump_url"]
                    image = attributes.get("pics")
                    image_link = image[0]["url"] if image else "http://example.com"
                else:
                    continue

                article = {
                    "aid": aid,
                    "bvid": bvid,
                    "title": name,
                    "summary": description,
                    "link": article_url,
                    "image_link": image_link,
                    "pub_time": time_obj
                }

                yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)
    

    async def get_login_qrcode(self, page):
        login_button_ele = page.locator("xpath=//div[@class='right-entry__outside go-login-btn']//div")
        await login_button_ele.click()
        # find login qrcode
        qrcode_img_selector = "//div[@class='login-scan-box']//img"
        elements = await page.wait_for_selector(selector=qrcode_img_selector)
        base64_qrcode_img = str(await elements.get_property("src"))
        return base64_qrcode_img

    @classmethod
    def create_bilibili_client(cls, user_agent: str, cookies):
        cookie_str, cookie_dict = environment.convert_cookies(cookies)
        headers = {"User-Agent": user_agent, "Cookie": cookie_str}
        return BilibiliClient(headers=headers, cookie_dict=cookie_dict)


class BilibiliClient:
    headers = {
        "User-Agent": None,
        "Cookie": None,
        "Origin": "https://www.bilibili.com",
        "Referer": "https://www.bilibili.com",
        "Content-Type": "application/json;charset=UTF-8"
    }
    
    def __init__(self, headers: dict[str, str], cookie_dict: dict[str, str], proxies=None, timeout=10):
        self.proxies = proxies
        self.timeout = timeout
        self.headers = BilibiliClient.headers | headers
        self._host = "https://api.bilibili.com"
        self.cookie_dict = cookie_dict
    
    def update_cookies(self, cookie_str, cookie_dict):
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def request(self, method, url, **kwargs) -> Any:
        async with httpx.AsyncClient(proxies=self.proxies) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)
        data: dict = response.json()
        if data.get("code") != 0:
            raise FailtoGet
        else:
            return data.get("data", {})

    async def get(self, uri: str, params=None, enable_params_sign: bool= True) -> dict:
        # if enable_params_sign:
        #     params = await self.pre_request_data(params)
        # if isinstance(params, dict):
        #     final_uri = (f"{uri}?{urlencode(params)}")
        final_uri = f"{uri}?{urlencode(params)}" if params else uri
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
        
    # async def pre_request_data(self, req_data: dict) -> dict:
    #     """请求参数签名
    #     需要从 localStorage 拿 wbi_img_urls 这参数，值如下：
    #     https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png-https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png
    #     """
    #     if not req_data:
    #         return {}
    #     img_key, sub_key = await self.get_wbi_keys()
    #     return BilibiliSign(img_key, sub_key).sign(req_data)

    # async def get_wbi_keys(self) -> Tuple[str, str]:
    #     """获取最新的 img_key 和 sub_key"""
    #     local_storage = await self.page.evaluate("() => window.localStorage")
    #     wbi_img_urls = local_storage.get("wbi_img_urls", "") or local_storage.get(
    #         "wbi_img_url") + "-" + local_storage.get("wbi_sub_url")
    #     if wbi_img_urls and "-" in wbi_img_urls:
    #         img_url, sub_url = wbi_img_urls.split("-")
    #     else:
    #         resp = await self.request(method="GET", url=self._host + "/x/web-interface/nav")
    #         img_url: str = resp['wbi_img']['img_url']
    #         sub_url: str = resp['wbi_img']['sub_url']
    #     img_key = img_url.rsplit('/', 1)[1].split('.')[0]
    #     sub_key = sub_url.rsplit('/', 1)[1].split('.')[0]
    #     return img_key, sub_key

    async def get_dynamic(self, page: int = 1, offset: str | None=None):
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

    async def get_video_info(self, aid: int | None = None, bvid: str | None = None) -> dict:
        """Bilibli web video detail api, aid 和 bvid任选一个参数"""
        if not any(aid, bvid):
            raise ValueError("请提供 aid 或 bvid 中的至少一个参数")

        uri = "/x/web-interface/view/detail"
        params = {"aid": aid} if aid else {"bvid": bvid}
        return await self.get(uri, params, enable_params_sign=False)


async def test():
    config = {
        "user_name": "AhFei",
        "image_root": "config_and_data_files/images",
        "screenshot_root": "config_and_data_files",
        "bili_context": "config_and_data_files/bili_context.json"
    }
    w = BiliFoDynamic(config)
    print(w.source_info)
    print(w.table_name)
    async for a in w.first_add():
        print(a)
    print("----------")
    async for a in w.get_new(datetime(2024, 5, 1)):
        print(a)
    print("----------")
    

if __name__ == "__main__":
    asyncio.run(test())
    # python -m dynamic_web_scraper.bili_follow_dynamic


