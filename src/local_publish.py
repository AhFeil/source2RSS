import logging
import asyncio

from src.website_scraper import FailtoGet, WebsiteScraper, LocateInfo
from src.generate_rss import generate_rss_from_collection

logger = logging.getLogger("local_publish")


async def save_articles(data, source_name, key4sort, article_source) -> bool:
    """有更新则返回真，不对外抛错"""
    all_article_etc = []
    try:
        async for a in article_source:
            # 每篇文章整合成一个文档，存入相应集合
            one_article_etc = {
                "article_infomation": a, 
                key4sort: a[key4sort]
            }
            all_article_etc.append(one_article_etc)
            logger.info(f"{source_name} have new article: {a['article_name']}")
    except asyncio.TimeoutError:
        logger.info(f"Processing {source_name} articles took too long.")
        return False
    except FailtoGet:
        logger.info(f"FailtoGet: Processing {source_name} 网络出错")
        return False
    except Exception as e:
        logger.warning("Unpredictable Exception: %s", e)
        return False

    store_a_new_one = False
    # 获得文章后，按从旧到新、从小到大的顺序放入 DB，这样即便中间出错中断，下次更新时会从中断处补充
    try:
        for one_article_etc in reversed(all_article_etc):
            data.store2database(source_name, one_article_etc)
            store_a_new_one = True
    except Exception as e:
        logger.warning("data.store2database(source_name, a) Unpredictable Exception: %s", e)
    return store_a_new_one

def format_source_name(t: str) -> str:
    """title会作为网址的一部分，因此不能出现空格等"""
    return t.replace(' ', '_')

async def goto_uniform_flow(data, instance: WebsiteScraper) -> str:
    """不对外抛错"""
    source_info, source_name, max_wait_time = instance.source_info, instance.table_name, instance.max_wait_time
    key4sort = source_info["key4sort"]
    # 确保 source 的元信息在数据库中
    data.exist_source_meta(source_info)
    collection = data.db[source_name]
    result = collection.find({}, {key4sort: 1, "article_infomation": 1}).sort(key4sort, -1).limit(1)   # 含有 '_id', 
    result = list(result)
    if result:
        flags: LocateInfo = {"article_name": result[0]["article_infomation"]["article_name"], key4sort: result[0][key4sort]} # type: ignore
        article_source = instance.get_new(flags)
    else:
        # 若是第一次，数据库中没有数据
        article_source = instance.first_add()

    got_new = False
    try:
        got_new = await asyncio.wait_for(save_articles(data, source_name, key4sort, article_source), max_wait_time)
    except asyncio.TimeoutError:
        logger.info(f"Processing {source_name} articles took too long when save_articles")

    source_name = format_source_name(source_info["title"])
    source_file_name = f"{source_name}.xml"
    if got_new | data.rss_is_absent(source_file_name):
        # 当有新内容或文件缺失的情况下，会生成 RSS 并保存
        rss_feed = generate_rss_from_collection(source_info, collection)
        cls_id_or_none = None if instance.__class__.is_variety else instance.__class__.__name__
        data.set_rss(source_file_name, rss_feed, cls_id_or_none)
    else:
        logger.info(f"{source_name} exists and doesn't update")

    return source_file_name
