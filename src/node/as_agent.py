import asyncio
import logging
import os
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Self

import socketio
from briefconf import BriefConfig
from fastapi import FastAPI, WebSocket

from preproc import Plugins
from src.crawl.crawler import ScraperNameAndParams, get_instance
from src.crawl.remote_crawl import remote_uniform_flow
from src.scraper.scraper_error import ScraperError


@dataclass(frozen=True)
class AgentConfig(BriefConfig):
    name: str
    client_url: str
    reconnection_attempts: int
    port: int
    enabled_scrapers: list[str]

    __slots__ = ("name", "client_url", "reconnection_attempts", "port", "enabled_scrapers")

    @classmethod
    def load(cls, config_path: str) -> Self:
        configs = cls._load_config(config_path)

        return cls(
            name=configs.get("name", "vfly2_agent"),
            client_url=configs.get("client_url", "http://127.0.0.1:8536"),
            reconnection_attempts=configs.get("reconnection_attempts", 0),
            port=configs.get("port", 8537),
            enabled_scrapers=configs.get("enabled_scrapers", []),
        )


configfile = os.getenv("SOURCE2RSS_AGENT_CONFIG_FILE", default="config_and_data_files/agent_config.yaml")
agent_config = AgentConfig.load(os.path.abspath(configfile))

logger = logging.getLogger("as_agent")

# 异步 Socket.IO 客户端
sio_agent = socketio.AsyncClient(
    reconnection=True,
    reconnection_attempts=agent_config.reconnection_attempts,
    reconnection_delay=3,
    reconnection_delay_max=60
)

@sio_agent.event
async def connect():
    logger.info("[AGENT] 已连接到服务器")
    supported_web_scrapers = tuple(set(agent_config.enabled_scrapers) & set(Plugins.get_all_id()))
    await sio_agent.emit("register", {
        "name": agent_config.name,
        "scrapers": supported_web_scrapers
    })

@sio_agent.event
async def register_ack(data):
    logger.info(f"[AGENT] 注册响应: {data}")


@dataclass
class Channel:
    channels: dict[str, asyncio.Future]

    def prepare(self, msg_id: str):
        if self.channels.get(msg_id):
            return
        fut = asyncio.get_running_loop().create_future()
        self.channels[msg_id] = fut

    async def send(self, payload: dict):
        await sio_agent.emit("crawl_reply", data=payload)

    async def recv(self, msg_id) -> dict | None:
        if fut := self.channels.get(msg_id):
            try:
                reply = await asyncio.wait_for(fut, timeout=180)
                return reply
            except asyncio.TimeoutError:
                self.channels.pop(msg_id, None)
                logger.info(f"[AGENT] 等待回复超时: {msg_id}")

    async def awake(self, request: dict):
        msg_id = request["msg_id"]
        if fut := self.channels.get(msg_id):
            if not fut.done():
                fut.set_result(request)
        else:
            await self.send({"msg": f"{msg_id} is not my channel"})

    def delete(self, msg_id: str):
        self.channels.pop(msg_id, None)


as_agent_channel = Channel(channels={})


@sio_agent.event
async def crawl(request: dict):
    logger.info(f"[AGENT] 收到任务: {request}")
    asyncio.create_task(remote_uniform_flow(as_agent_channel, request))


@sio_agent.event
async def go_on(request: dict):
    await as_agent_channel.awake(request)


@sio_agent.event
async def disconnect():
    logger.info("[AGENT] 与服务器断开连接")


async def start_agent():
    await sio_agent.connect(agent_config.client_url)
    await sio_agent.wait()


# 下面是直连用的

app = FastAPI()

def normalize_datetime_flags(flags: dict) -> dict:
    for key in ("pub_time", "time4sort"):
        if key in flags and not isinstance(flags[key], datetime):
            flags[key] = datetime.fromtimestamp(flags[key])
    return flags

@app.websocket("/ws_connect")
async def connect_agent(websocket: WebSocket):
    # TODO 合并相同代码
    await websocket.accept()
    try:
        request = await websocket.receive_json()
        msg_id = request["msg_id"]
        over_payload = {"msg_id": msg_id, "over": True}
        logger.info(f"[AGENT] Receive task of {request['cls_id']}, params is {request['params']}")
        scrapers = ScraperNameAndParams.create(request["cls_id"], (request["params"], ), 10, True)
        if not scrapers:
            await websocket.send_json(over_payload)
            return

        instance = await get_instance(scrapers[0])
        if not instance:
            await websocket.send_json(over_payload)
            return

        payload = {"msg_id": msg_id} | instance.source_info
        await websocket.send_json(payload)

        request = await websocket.receive_json()
        if not request or request.get("over"):
            return
        if not request.get("continue"):
            return
        flags = normalize_datetime_flags(request["flags"])
        async for a in instance.get(flags): # type: ignore
            for key in a:
                if isinstance(a[key], datetime):
                    a[key] = a[key].timestamp()
            payload = {"msg_id": msg_id} | {"article": a}
            await websocket.send_json(payload)

        await websocket.send_json(over_payload)
    except ScraperError as e:
        logger.error(f"[AGENT] Error: {e}")
        await websocket.send_json(over_payload)
    except Exception as e:
        logger.error(f"[AGENT] Error: {e}")
        logger.error(f"[AGENT] Full traceback:\n{traceback.format_exc()}")
    finally:
        await websocket.close()
        logger.info("[AGENT] Client disconnected")


if __name__ == "__main__":
    if agent_config.port:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=agent_config.port)
    else:
        asyncio.run(start_agent())
    # python -m src.node.as_agent
