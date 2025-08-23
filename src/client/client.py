import base64
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Self, TypedDict

import httpx

logger = logging.getLogger("post2RSS")


class S2RProfile(TypedDict):
    ip_or_domain: str
    port: int
    username: str
    password: str
    source_name: str


@dataclass
class Source2RSSClient:
    post_url: str
    src_url: str
    headers: dict[str, str]

    __slots__ = ("post_url", "src_url", "headers")

    timeout: ClassVar[httpx.Timeout] = httpx.Timeout(10.0, read=10.0)

    @classmethod
    def create(cls, cfg: S2RProfile, send_test: bool=False) -> Self:
        """如果 send_test 为真，则在创建后发送一个文章，用于测试功能"""
        root_url = f"http://{cfg['ip_or_domain']}:{cfg['port']}"
        post_url = f"{root_url}/post_src/{cfg['source_name']}/"
        src_url = f"{root_url}/query_rss/{cfg['source_name']}.xml/#"
        credentials = f"{cfg['username']}:{cfg['password']}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        }

        client = cls(post_url, src_url, headers)
        print(os.getenv("SOURCE2RSS_CLIENT_SEND_TEST"))
        if send_test or bool(os.getenv("SOURCE2RSS_CLIENT_SEND_TEST")):
            import asyncio
            title = f"This is a test article from {cfg['source_name']}"
            summary = "This article was posted because you set the environment variable 'SOURCE2RSS_CLIENT_SEND_TEST' or pass True for 'send_test', so when the source2RSS client was being creating, it will send a test article."
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                client.sync_post_article(title, summary)
            else:
                loop.create_task(client.post_article(title, summary))
            logger.info("Sending test article...")
        return client

    async def post_article(self, title: str, summary: str) -> httpx.Response | None:
        """不引发异常"""
        data_raw = (Source2RSSClient._assamble_article(self.src_url, title, summary), )
        async with httpx.AsyncClient(headers=self.headers, timeout=Source2RSSClient.timeout) as client:
            try:
                response = await client.post(url=self.post_url, json=data_raw)
            except Exception as e:
                logger.warning(f"exception of Source2RSSClient - post_article: {e}")
            else:
                return response

    def sync_post_article(self, title: str, summary: str) -> httpx.Response | None:
        """不引发异常"""
        data_raw = (Source2RSSClient._assamble_article(self.src_url, title, summary), )
        with httpx.Client(headers=self.headers, timeout=Source2RSSClient.timeout) as client:
            try:
                response = client.post(url=self.post_url, json=data_raw)
            except Exception as e:
                logger.warning(f"exception of Source2RSSClient - post_article: {e}")
            else:
                return response

    @staticmethod
    def _assamble_article(src_url: str, title: str, summary: str) -> dict:
        pub_time = datetime.now().timestamp()
        return {
            "title": title,
            "link": src_url + str(pub_time), # 添加时间戳是因为 ttrss 会以网址作为唯一标识，因此网址若一样，只会读到一条消息，其他都会被掩盖
            "summary": summary,
            "content": summary,
            "pub_time": pub_time
        }
