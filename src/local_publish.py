import logging
import asyncio

from src.website_scraper import FailtoGet, WebsiteScraper, LocateInfo, Sequence
from src.generate_rss import generate_rss
from configHandle import post2RSS

logger = logging.getLogger("local_publish")


async def save_articles(data, source_name, article_source) -> bool:
    """
    有更新则返回真，不对外抛错
    1. 有几篇新文章返回，无异常，应该返回有更新
    2. 有几篇新文章返回，有异常，应该返回有更新
    3. 没文章返回，无异常，应该返回没有更新
    4. 第一篇文章返回时发生异常，应该返回没有更新
    """
    store_a_new_one = False
    try:
        async for a in article_source:
            # 每篇文章整合成一个文档，存入相应集合
            data.db_intf.store2database(source_name, a)
            store_a_new_one = True
            logger.info(f"{source_name} have new article: {a['title']}")
    except asyncio.TimeoutError:
        logger.info(f"Processing {source_name} articles took too long.")
    except FailtoGet:
        logger.info(f"FailtoGet: Processing {source_name} 网络出错")
    except Exception as e:
        msg = f"Unpredictable Exception when get and save article of {source_name}: {e}"
        logger.exception(msg)
        await post2RSS("error log of save_articles", msg)
    finally:
        return store_a_new_one

async def goto_uniform_flow(data, instance: WebsiteScraper, amount: int) -> str:
    """不对外抛错。让抓取器运行一次，把数据保存和转换"""
    source_info, source_name, max_wait_time = instance.source_info, instance.table_name, instance.max_wait_time
    key4sort = source_info["key4sort"]
    # 确保 source 的元信息在数据库中
    data.db_intf.exist_source_meta(source_info)
    result = data.db_intf.get_top_n_articles_by_key(source_name, 1, key4sort)
    if result:
        flags: LocateInfo = {"article_title": result[0]["title"], key4sort: result[0][key4sort]} # type: ignore
        sequence = Sequence.PREFER_OLD2NEW
    else: # 若是第一次，数据库中没有数据
        flags: LocateInfo = {"amount": amount} # type: ignore
        sequence = Sequence.PREFER_NEW2OLD

    got_new = False
    try:
        got_new = await asyncio.wait_for(save_articles(data, source_name, instance.get(flags, sequence)), max_wait_time)
    except asyncio.TimeoutError:
        logger.info(f"Processing {source_name} articles took too long when save_articles")

    if got_new | data.rss_cache.rss_is_absent(source_name):
        # 当有新内容或文件缺失的情况下，会生成 RSS 并保存
        result = data.db_intf.get_top_n_articles_by_key(source_name, 50, key4sort)
        rss_feed = generate_rss(source_info, result)
        rss_json = {"source_info": source_info, "articles": result}
        cls_id_or_none = None if instance.__class__.is_variety else instance.__class__.__name__
        data.rss_cache.set_rss(source_name, rss_feed, rss_json, cls_id_or_none, source_info["access"])
        logger.info(f"{source_name} updates")
    else:
        logger.info(f"{source_name} exists and doesn't update")

    return source_name
