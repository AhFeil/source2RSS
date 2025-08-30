"""由服务端直连的 agent"""
import asyncio
import logging
import os
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Self

from briefconf import BriefConfig
from fastapi import FastAPI, WebSocket

from src.crawl.crawl_error import CrawlRepeatError
from src.crawl.crawler import ScraperNameAndParams, discard_scraper, get_instance
from src.scraper.scraper_error import ScraperError


@dataclass(frozen=True, slots=True)
class AgentConfig(BriefConfig):
    name: str
    port: int
    enabled_scrapers: list[str]

    @classmethod
    def load(cls, config_path: str) -> Self:
        configs = cls._load_config(config_path)
        return cls(
            name=configs.get("name", "vfly2_agent"),
            port=configs.get("port", 8537),
            enabled_scrapers=configs.get("enabled_scrapers", []),
        )

configfile = os.getenv("SOURCE2RSS_AGENT_CONFIG_FILE", default="config_and_data_files/agent_config.yaml")
agent_config = AgentConfig.load(os.path.abspath(configfile))

logger = logging.getLogger("as_d_agent")

app = FastAPI()

def normalize_datetime_flags(flags: dict) -> dict:
    for key in ("pub_time", "time4sort"):
        if key in flags and not isinstance(flags[key], datetime):
            flags[key] = datetime.fromtimestamp(flags[key])
    return flags

# TODO 重复代码
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
        scraper = scrapers[0]
        instance = await get_instance(scraper)
        if not instance:
            await websocket.send_json(over_payload)
            return

        try:
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
        finally:
            asyncio.create_task(discard_scraper(scraper))
            await instance.destroy()
    except CrawlRepeatError:
        logger.info("[AGENT] Client disconnected")
        await websocket.send_json(over_payload)
    except ScraperError as e:
        logger.error(f"[AGENT] Error: {e}")
        logger.error(f"[AGENT] Full traceback:\n{traceback.format_exc()}")
        await websocket.send_json(over_payload)
    except Exception as e:
        logger.error(f"[AGENT] Error: {e}")
        logger.error(f"[AGENT] Full traceback:\n{traceback.format_exc()}")
    finally:
        await websocket.close()
        logger.info("[AGENT] Client disconnected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=agent_config.port)
    # python -m src.node.as_d_agent
