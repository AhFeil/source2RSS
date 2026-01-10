import asyncio
from datetime import datetime

from src.crawl.crawler import ScraperNameAndParams, discard_scraper, get_instance


async def remote_uniform_flow(as_agent_channel, request: dict):
    try:
        msg_id = request["msg_id"]
        as_agent_channel.prepare(msg_id)
        scrapers = ScraperNameAndParams.create(request["cls_id"], (request["params"], ), 10, True)
        if not scrapers:
            payload = {"msg_id": msg_id, "over": True}
            await as_agent_channel.send(payload)
            return
        scraper = scrapers[0]
        instance = await get_instance(scraper)
        if not instance:
            payload = {"msg_id": msg_id, "over": True}
            await as_agent_channel.send(payload)
            return
        try:
            payload = {"msg_id": msg_id} | instance.source_info
            await as_agent_channel.send(payload)
            # while True:
            res = await as_agent_channel.recv(msg_id)
            if not res or res.get("over"):
                return
            if res.get("continue"):
                flags = res["flags"]
                if flags.get("pub_time") and not isinstance(flags["pub_time"], datetime): # TODO 为什么浏览器触发的传来的 pub_time 是 datetime.datetime(2025, 8, 8, 6, 52, 8, 857000)
                    flags["pub_time"] = datetime.fromtimestamp(flags["pub_time"])
                if flags.get("time4sort") and not isinstance(flags["time4sort"], datetime):
                    flags["time4sort"] = datetime.fromtimestamp(flags["time4sort"])

                articles = []
                async for a in instance.get(flags):
                    for key in a:
                        if isinstance(a[key], datetime):
                            a[key] = a[key].timestamp()
                    articles.append(a)
                payload = {"msg_id": msg_id} | {"articles": articles}
                await as_agent_channel.send(payload)
        finally:
            asyncio.create_task(discard_scraper(scraper))
            await instance.destroy()
    finally:
        as_agent_channel.delete(msg_id)
