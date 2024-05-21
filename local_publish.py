import logging
import asyncio

from website_scraper.example import FailtoGet
from generate_rss import generate_rss_from_collection

logger = logging.getLogger("local_publish")


async def save_articles(data, source_name, key4sort, article_source) -> bool:
    got_new = False
    async for a in article_source:
        # 每篇文章整合成一个文档，存入相应集合
        one_article_etc = {
            "article_infomation": a, 
            key4sort: a[key4sort]
        }
        data.store2database(source_name, one_article_etc)
        logger.info(f"{source_name} have new article: {a['article_name']}")
        got_new = True
    return got_new

async def goto_uniform_flow(config, data, instance):
    # 确保 source 的元信息在数据库中
    source_info, source_name = instance.source_info, instance.table_name
    key4sort = source_info["key4sort"]
    data.exist_source_meta(source_info)

    collection = data.db[source_name]
    result = collection.find({}, {key4sort: 1}).sort(key4sort, -1).limit(1)   # 含有 '_id', 
    result = list(result)
    last_update_flag = result[0][key4sort] if result else False
    
    # 若是第一次，数据库中没有数据
    article_source = instance.first_add() if not last_update_flag else instance.get_new(last_update_flag)
    
    try:
        got_new = await asyncio.wait_for(save_articles(data, source_name, key4sort, article_source), 60)
    except asyncio.TimeoutError:
        got_new = False
        logger.info(f"Processing {source_name} articles took too long.")
    except FailtoGet:
        got_new = False
        logger.info(f"FailtoGet: Processing {source_name} 网络出错")

    # 生成 RSS 并保存到目录
    if got_new:
        generate_rss_from_collection(source_info, collection, config.rss_dir)
    else:
        logger.info(f"{source_name} didn't update")