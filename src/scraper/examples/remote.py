import asyncio
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator, Self

import websockets

from dataHandle import Agent, D_Agent
from src.scraper.scraper import WebsiteScraper
from src.scraper.scraper_error import CreateButRequestFail, CreateByLackAgent


class AgentCon(ABC):
    @classmethod
    @abstractmethod
    async def create(cls, agent: D_Agent, msg_id: str) -> Self:
        raise NotImplementedError()

    @abstractmethod
    async def send(self, data: dict, event=""):
        raise NotImplementedError()

    @abstractmethod
    async def recv(self) -> dict | None:
        raise NotImplementedError()

    async def recv_iter(self) -> AsyncGenerator[dict, None]:
        res = await self.recv()
        if res and res.get("articles"):
            for a in res["articles"]:
                yield {"article": a}

    async def destroy(self):
        pass

@dataclass
class D_AgentConnect(AgentCon):
    ws: websockets.WebSocketClientProtocol
    msg_id: str

    @classmethod
    async def create(cls, agent: D_Agent, msg_id: str) -> Self:
        try:
            ws = await websockets.connect(agent.uri)
        except Exception:
            raise CreateButRequestFail()
        return cls(ws, msg_id)

    async def send(self, data: dict, event=""):
        data["msg_id"] = self.msg_id
        await self.ws.send(json.dumps(data))

    async def recv(self) -> dict | None:
        reply = await self.ws.recv()
        reply = json.loads(reply)
        if reply.get("over"):
            return
        reply.pop("msg_id", None)
        return reply

    async def recv_iter(self) -> AsyncGenerator[dict, None]:
        async for res in self.ws:
            reply = json.loads(res)
            if reply.get("over"):
                return
            reply.pop("msg_id", None)
            yield reply

    async def destroy(self):
        try:
            if not self.ws.closed:
                await self.ws.send(json.dumps({"msg_id": self.msg_id, "over": True}))
        except (websockets.ConnectionClosed, OSError, asyncio.IncompleteReadError):
            pass  # 连接已断，无需处理
        finally:
            await self.ws.close()

@dataclass
class R_AgentConnect(AgentCon):
    agent: Agent
    msg_id: str

    @classmethod
    async def create(cls, agent: Agent, msg_id: str) -> Self:
        return cls(agent, msg_id)

    async def send(self, data: dict, event: str):
        if not data.get("over"):
            fut = asyncio.get_running_loop().create_future()
            self.agent.pending_futures[self.msg_id] = fut
        data["msg_id"] = self.msg_id
        await self.agent.sio.emit(event, data, to=self.agent.sid)

    async def recv(self) -> dict | None:
        fut = self.agent.pending_futures.get(self.msg_id)
        if not fut:
            return

        try:
            reply = await asyncio.wait_for(fut, timeout=600)
        except asyncio.TimeoutError:
            self.agent.pending_futures.pop(self.msg_id, None)
            return

        self.agent.pending_futures.pop(self.msg_id, None)
        if reply.get("over"):
            return
        return reply

    async def destroy(self):
        self.agent.pending_futures.pop(self.msg_id, None)


class Remote(WebsiteScraper):
    @classmethod
    async def create(cls, agents: tuple[Agent | D_Agent, ...], cls_id: str, *params) -> Self:
        """
        Args:
            cls_id: 抓取类的标识，一般是类名
        """
        if not agents:
            raise CreateByLackAgent()
        msg_id = Remote.make_short_msg_id(cls_id, params)
        commission = {"cls_id": cls_id, "params": params} # 根据这两个参数生成 msg_id
        for agent in agents:
            if isinstance(agent, D_Agent):
                con = await D_AgentConnect.create(agent, msg_id)
            elif isinstance(agent, Agent):
                con = await R_AgentConnect.create(agent, msg_id)
            else:
                raise CreateByLackAgent()
            await con.send(commission, "crawl")
            source = await con.recv()
            if source:
                return cls(source, con, cls_id, params)
        raise CreateByLackAgent()

    def __init__(self, source: dict, con: AgentCon, cls_id: str, params) -> None:
        super().__init__()
        self.source, self.con, self.cls_id, self.params = source, con, cls_id, params

    def _source_info(self):
        return self.source

    @classmethod
    async def _parse(cls, flags, con: AgentCon, cls_id: str, params) -> AsyncGenerator[dict, None]:
        flags = dict(flags)
        for key in flags:
            if isinstance(flags[key], datetime):
                flags[key] = flags[key].timestamp()
        cls._logger.info(f"[Remote] {cls_id} start to parse")

        commission = {"cls_id": cls_id, "params": params, "flags": flags, "continue": True}

        await con.send(commission, "go_on")
        async for reply in con.recv_iter():
            a = reply["article"]
            cls._logger.info(f"[Remote] {cls_id} have new article")
            if a.get("pub_time"):
                a["pub_time"] = datetime.fromtimestamp(a["pub_time"])
            if a.get("time4sort"):
                a["time4sort"] = datetime.fromtimestamp(a["time4sort"])
            yield a

        # await send("go_on", {"over": True})

    def _custom_parameter_of_parse(self) -> tuple:
        return (self.con, self.cls_id, self.params)

    async def destroy(self) -> None:
        Remote._logger.info(f"[Remote] {self.cls_id} close websocket")
        await self.con.destroy()

    @staticmethod
    def make_short_msg_id(cls_id, params):
        commission = {"cls_id": cls_id, "params": params}
        # 固定 JSON 序列化结果
        serialized = json.dumps(commission, sort_keys=True, separators=(",", ":"))
        # 取 MD5 哈希并截取前 16 个字符
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()[:16]
