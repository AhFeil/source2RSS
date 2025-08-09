import hashlib
import json
from datetime import datetime
from typing import AsyncGenerator, Self

from dataHandle import Agent
from src.scraper.scraper import WebsiteScraper
from src.scraper.scraper_error import CreateByLackAgent


class Remote(WebsiteScraper):
    @classmethod
    async def create(cls, agents: tuple[Agent, ...], cls_id: str, *params) -> Self:
        """
        Args:
            cls_id: 抓取类的标识，一般是类名
        """
        if not agents:
            raise CreateByLackAgent()
        msg_id = Remote.make_short_msg_id(cls_id, params)
        commission = {"cls_id": cls_id, "params": params} # 根据这两个参数生成 msg_id
        for agent in agents:
            async with agent as (send, recv): # 不并发
                if not send or not recv:
                    continue
                await send(msg_id, "crawl", commission)
                source = await recv(msg_id)
                # raise CreateButRequestFail()
                if source:
                    return cls(source, agent, cls_id, params)
        raise CreateByLackAgent()

    def __init__(self, source: dict, agent: Agent, cls_id: str, params) -> None:
        super().__init__()
        self.source, self.agent, self.cls_id, self.params = source, agent, cls_id, params

    def _source_info(self):
        return self.source

    @classmethod
    async def _parse(cls, flags, agent: Agent, cls_id: str, params) -> AsyncGenerator[dict, None]:
        for key in flags:
            if isinstance(flags[key], datetime):
                flags[key] = flags[key].timestamp()
        cls._logger.info(f"[Remote] {cls_id} start to parse")

        msg_id = Remote.make_short_msg_id(cls_id, params)
        commission = {"cls_id": cls_id, "params": params, "flags": flags, "continue": True}
        async with agent as (send, recv):
            if not send or not recv:
                return
            await send(msg_id, "go_on", commission)
            res = await recv(msg_id)

        if res and res.get("articles"):
            cls._logger.info(f"[Remote] {cls_id} have new articles")
            for a in res["articles"]:
                if a.get("pub_time"):
                    a["pub_time"] = datetime.fromtimestamp(a["pub_time"])
                if a.get("time4sort"):
                    a["time4sort"] = datetime.fromtimestamp(a["time4sort"])
                yield a
        # await send("go_on", {"over": True})

    def _custom_parameter_of_parse(self) -> tuple:
        return (self.agent, self.cls_id, self.params)

    @staticmethod
    def make_short_msg_id(cls_id, params):
        commission = {"cls_id": cls_id, "params": params}
        # 固定 JSON 序列化结果
        serialized = json.dumps(commission, sort_keys=True, separators=(",", ":"))
        # 取 MD5 哈希并截取前 16 个字符
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()[:16]
