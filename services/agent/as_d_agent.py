"""由服务端直连的 agent"""
import asyncio
import logging
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, WebSocket

from source2rss_fw.crawl import ScraperNameAndParams, Crawler
from source2rss_fw.crawl.crawl_error import CrawlRepeatError
from source2rss_fw.plugin import Plugins
from source2rss_fw.scraper.scraper_error import ScraperError

from config_handle import config

logger = logging.getLogger("as_d_agent")

crawler = Crawler.create(180, 30, ZoneInfo("Asia/Shanghai"), None)

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
        scrapers = ScraperNameAndParams.create(request["cls_id"], (request["params"], ), 10, 100, 30, lambda _ : "self", lambda _ : "", True)
        if not scrapers:
            await websocket.send_json(over_payload)
            return
        scraper = scrapers[0]
        instance = await crawler.get_scraper_instance(scraper)
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
            asyncio.create_task(crawler.discard_scraper(scraper))
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

Plugins.load_plugins(config.enabled_web_scraper, (config.root_dir,))
