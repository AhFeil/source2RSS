import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import socketio
from fastapi import FastAPI, WebSocket

from preproc import Plugins, config
from src.crawl.crawler import ScraperNameAndParams, get_instance
from src.crawl.remote_crawl import remote_uniform_flow

logger = logging.getLogger("as_agent")

# 异步 Socket.IO 客户端
sio_agent = socketio.AsyncClient(reconnection=True, reconnection_attempts=config.as_agent.get("reconnection_attempts", 1), reconnection_delay=3, reconnection_delay_max=60)

@sio_agent.event
async def connect():
    logger.info("[AGENT] 已连接到服务器")
    supported_web_scrapers = tuple(set(config.as_agent["enabled_scrapers"]) & set(Plugins.get_all_id()))
    await sio_agent.emit("register", {
        "name": config.as_agent["name"],
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
    await sio_agent.connect(config.as_agent["client_url"])
    await sio_agent.wait()


# 下面是直连用的

app = FastAPI()

@app.websocket("/ws_connect")
async def connect_agent(websocket: WebSocket):
    # TODO 合并相同代码
    await websocket.accept()
    try:
        request = await websocket.receive_json()
        msg_id = request["msg_id"]
        scrapers = ScraperNameAndParams.create(request["cls_id"], (request["params"], ), 10, True)
        if not scrapers:
            payload = {"msg_id": msg_id, "over": True}
            await websocket.send_json(payload)
            return

        instance = await get_instance(scrapers[0])
        if not instance:
            payload = {"msg_id": msg_id, "over": True}
            await websocket.send_json(payload)
            return

        payload = {"msg_id": msg_id} | instance.source_info
        await websocket.send_json(payload)

        res = await websocket.receive_json()
        if not res or res.get("over"):
            return
        if res.get("continue"):
            flags = res["flags"]
            if flags.get("pub_time") and not isinstance(flags["pub_time"], datetime):
                flags["pub_time"] = datetime.fromtimestamp(flags["pub_time"])
            if flags.get("time4sort") and not isinstance(flags["time4sort"], datetime):
                flags["time4sort"] = datetime.fromtimestamp(flags["time4sort"])

            async for a in instance.get(flags):
                for key in a:
                    if isinstance(a[key], datetime):
                        a[key] = a[key].timestamp()
                payload = {"msg_id": msg_id} | {"article": a}
                await websocket.send_json(payload)

        payload = {"msg_id": msg_id, "over": True}
        await websocket.send_json(payload)
    except Exception as e:
        logger.error(f"[AGENT] Error: {e}")
    finally:
        await websocket.close()
        logger.info("[AGENT] Client disconnected")


if __name__ == "__main__":
    if port := config.as_agent.get("port"):
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        asyncio.run(start_agent())
    # python -m src.node.as_agent
