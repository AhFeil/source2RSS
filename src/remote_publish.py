import logging
import asyncio
import json
import httpx
from datetime import datetime

from src.website_scraper import FailtoGet

logger = logging.getLogger("remote_publish")


async def exist_source_meta(source_info, url):
    async with httpx.AsyncClient() as client:
        await client.post(url=url, data=json.dumps(source_info))

async def get_rss_info(url):
    async with httpx.AsyncClient() as client:
        return await client.get(url=url)


async def push2rss(articles, pub_method, url):
    # 将 datetime 对象转化为时间戳
    for a in articles:
        for key, val in a.items():
            if isinstance(val, datetime):
                a[key] = val.timestamp()
    
    async with httpx.AsyncClient() as client:
        data = {"articles": articles, "pub_method": pub_method}
        return await client.post(url=url, data=json.dumps(data))


async def save_articles(source_name, key4sort, article_source, url) -> bool:
    got_new = False
    articles = []
    pub_method = {"key4sort": key4sort}

    try:
        async for a in article_source:
            articles.append(a)
            logger.info(f"{source_name} have new article: {a['title']}")
            got_new = True
    except asyncio.TimeoutError:
        logger.info(f"Processing {source_name} articles took too long.")
    except FailtoGet:
        logger.info(f"FailtoGet: Processing {source_name} 网络出错")
    except Exception as e:
        logger.warning("Processing %s Unpredictable Exception: %s", source_name, e)

    if got_new:
        try:
            res = await push2rss(articles, pub_method, url)
        except Exception as e:
            logger.warning("Server is inaccessible %s", e)
        else:
            logger.info(f"{source_name} return info {res.content}")
    else:
        logger.info(f"{source_name} didn't update")

async def goto_remote_flow(config, data, instance, url):
    # 确保 source 的元信息在数据库中
    source_info, source_name = instance.source_info, instance.table_name
    key4sort = source_info["key4sort"]
    await exist_source_meta(source_info, f"{url}rss_info/test/{source_name}")

    rss_info = await get_rss_info(f"{url}rss_info/test/{source_name}/")
    rss_info = rss_info.json()
    last_update_flag = rss_info["last_update_flag"]
    if key4sort in {"pub_time"}:
        last_update_flag = datetime.fromtimestamp(last_update_flag)

    # 若是第一次，数据库中没有数据
    article_source = instance.first_add() if not last_update_flag else instance.get_new(last_update_flag)

    await asyncio.wait_for(save_articles(source_name, key4sort, article_source, f"{url}rss_items/test/{source_name}/"), 120)



if __name__ == "__main__":

    data = {}

    with httpx.Client() as client:
        res = client.post(url="", data=json.dumps(data))
        print(res.content)
