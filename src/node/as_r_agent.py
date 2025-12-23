import asyncio
import logging
import os
import random
from dataclasses import dataclass
from typing import Self

import socketio
from briefconf import BriefConfig
from socketio.exceptions import ConnectionError as ConnectionError_

from data_handle import Plugins
from src.crawl.remote_crawl import remote_uniform_flow


@dataclass(frozen=True, slots=True)
class AgentConfig(BriefConfig):
    name: str
    client_url: str
    reconnection_attempts: int
    enabled_scrapers: list[str]

    @classmethod
    def load(cls, config_path: str) -> Self:
        configs = cls._load_config(config_path)
        return cls(
            name=configs["name"],
            client_url=configs["client_url"],
            reconnection_attempts=configs.get("reconnection_attempts", 0),
            enabled_scrapers=configs.get("enabled_scrapers", []),
        )


configfile = os.getenv("SOURCE2RSS_AGENT_CONFIG_FILE", default="config_and_data_files/agent_config.yaml")
agent_config = AgentConfig.load(os.path.abspath(configfile))

logger = logging.getLogger("as_r_agent")

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
    retry_delay = agent_config.reconnection_attempts or 1000
    max_retry_delay = 60
    while True:
        try:
            await sio_agent.connect(agent_config.client_url)
            retry_delay = 5  # 成功后重置重试时间
            await sio_agent.wait()
        except ConnectionError_ as e:
            logger.warning("连接失败: %s", str(e))
            wait_time = retry_delay + random.uniform(0, 2)
            logger.info("等待 %.2f 秒后重试...", wait_time)
            await asyncio.sleep(wait_time)
            retry_delay = min(retry_delay * 2, max_retry_delay)  # 指数增长
        finally:
            if sio_agent.connected:
                await sio_agent.disconnect()

if __name__ == "__main__":
    asyncio.run(start_agent())
    # python -m src.node.as_r_agent
