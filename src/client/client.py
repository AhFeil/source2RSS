import base64
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Self, TypedDict

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

    @classmethod
    def create(cls, cfg: S2RProfile) -> Self:
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
        return cls(post_url, src_url, headers)

    async def post_article(self, title: str, summary: str) -> httpx.Response | None:
        """不引发异常"""
        timeout = httpx.Timeout(10.0, read=10.0)
        data_raw = ({
                "title": title,
                "link": self.src_url + str(datetime.now().timestamp()), # 添加时间戳是因为 ttrss 会以网址作为唯一标识，因此网址若一样，只会读到一条消息，其他都会被掩盖
                "summary": summary,
                "content": summary,
                "pub_time": datetime.now().timestamp()
            }, )
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url=self.post_url, headers=self.headers, json=data_raw, timeout=timeout)
            except Exception as e:
                logger.warning(f"exception of Source2RSSClient - post_article: {e}")
            else:
                return response
