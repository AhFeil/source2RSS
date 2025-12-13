import asyncio
import logging

from config_handle import config
from src.scraper import LocateInfo, Sequence, WebsiteScraper
from src.scraper.scraper_error import FailtoGet

from .generate_rss import generate_rss

logger = logging.getLogger("local_publish")


async def save_articles(data, source_name, article_source, store_a_new_one: list[bool]):
    """
    有更新则标记为真
    1. 有几篇新文章返回，无异常，应该返回有更新
    2. 有几篇新文章返回，有异常，应该返回有更新
    3. 没文章返回，无异常，应该返回没有更新
    4. 第一篇文章返回时发生异常，应该返回没有更新
    """
    store_a_new_one[0] = False
    try:
        async for a in article_source:
            # 每篇文章整合成一个文档，存入相应集合
            data.db_intf.store2database(source_name, a)
            store_a_new_one[0] = True
            logger.debug("%s have new article: %s", source_name, a['title'])
    except asyncio.TimeoutError:
        logger.info("Processing %s articles took too long.", source_name)
    except FailtoGet:
        logger.info("FailtoGet: Processing %s 网络出错", source_name)

async def goto_uniform_flow(data, instance: WebsiteScraper, amount: int) -> str:
    """让抓取器运行一次，把数据保存和转换"""
    source_info, max_wait_time = instance.source_info, instance.max_wait_time
    source_name, key4sort = source_info["table_name"], source_info["key4sort"]
    # 确保 source 的元信息在数据库中
    data.db_intf.exist_source_meta(source_info)
    result = data.db_intf.get_top_n_articles_by_key(source_name, 1, key4sort)
    if result:
        flags: LocateInfo = {"article_title": result[0]["title"], key4sort: result[0][key4sort]} # type: ignore
        sequence = Sequence.PREFER_OLD2NEW
    else: # 若是第一次，数据库中没有数据
        flags: LocateInfo = {"amount": amount} # type: ignore
        sequence = Sequence.PREFER_NEW2OLD

    got_new = [False]
    try:
        await asyncio.wait_for(save_articles(data, source_name, instance.get(flags, sequence), got_new), max_wait_time)
    except asyncio.TimeoutError:
        logger.info("Processing %s articles took too long when save_articles", source_name)

    if got_new[0] or data.rss_cache.rss_is_absent(source_name):
        # 当有新内容或文件缺失的情况下，会生成 RSS 并保存
        result = data.db_intf.get_top_n_articles_by_key(source_name, config.get_max_rss_items(instance.__class__.__name__), key4sort)
        rss_feed = generate_rss(source_info, result)
        rss_json = {"source_info": source_info, "articles": result}
        for a in result:
            a["pub_time"] = str(a["pub_time"])
            a["time4sort"] = str(a["time4sort"])  # TODO
        data.rss_cache.set_rss(source_name, rss_feed, rss_json, source_info["access"])
        logger.info("%s updates", source_name)
    else:
        logger.debug("%s exists and doesn't update", source_name)

    return source_name
