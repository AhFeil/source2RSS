import logging

import socketio

from configHandle import config
from dataHandle import data

logger = logging.getLogger("as_client")

# 创建 Socket.IO 服务器
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

@sio.event
async def connect(sid: str, environ):
    logger.info("[CLIENT] 远端连接: %s", sid)

@sio.event
async def register(sid: str, resume: dict):
    name = resume.get("name")
    scrapers = resume.get("scrapers")
    if name is None or scrapers is None:
        await sio.emit("register_ack", {"status": "fail", "msg": "lack name or scrapers"}, to=sid)
        return

    if not config.is_a_known_agent(name):
        await sio.emit("register_ack", {"status": "fail", "msg": "you are not known agent"}, to=sid)
        return

    res, msg = data.agents.register(sid, name, scrapers, sio)
    if res:
        await sio.emit("register_ack", {"status": "ok"}, to=sid)
    else:
        await sio.emit("register_ack", {"status": "fail", "msg": msg}, to=sid)

@sio.event
async def disconnect(sid: str):
    logger.info("[CLIENT] 远端断开: %s", sid)
    data.agents.delete(sid)

@sio.event
async def crawl_reply(sid, payload):
    msg_id = payload.pop("msg_id")
    agent = data.agents.get_agent(sid)
    if agent and msg_id in agent.pending_futures:
        fut = agent.pending_futures[msg_id]
        if not fut.done():
            fut.set_result(payload)  # 唤醒等待的协程
