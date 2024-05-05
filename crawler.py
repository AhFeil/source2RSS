import logging
import asyncio
import signal
from itertools import chain

from generate_rss import generate_rss

logger = logging.getLogger("crawler")


async def one_website(config, data, cls):
    """对某个网站的文章进行更新"""
    instance = cls()
    sort_by_key = cls.sort_by_key
    # 确保 source 的元信息在数据库中
    source_info, source_name = instance.get_source_info(), instance.get_table_name()
    data.exist_source_meta(source_info)
    collection = data.db[source_name]

    result = collection.find({}, {sort_by_key: 1}).sort(sort_by_key, -1).limit(1)   # 含有 '_id', 
    result = list(result)
    last_update_flag = result[0][sort_by_key] if result else False
    
    got_new = False
    if not last_update_flag:
        # 若是第一次，数据库中没有数据
        got_new = True
        article_source = instance.first_add()
    else:
        article_source = instance.get_new(last_update_flag)
    
    async for a in article_source:
        # 每篇文章整合成一个文档，存入相应集合
        one_article_etc = {
            "article_infomation": a, 
            sort_by_key: a[sort_by_key]
        }
        data.store2database(source_name, one_article_etc)
        logger.info(f"{source_name} have new article: {a['article_name']}")
        got_new = True
    
    # 生成 RSS 并保存到目录
    if got_new:
        generate_rss(collection, sort_by_key, config.rss_dir, data.db[config.source_meta])
    else:
        logger.info(f"{source_name} didn't update")


async def chapter_mode(config, data, init_params, cls):
    """对多实例的抓取器，比如番茄的小说，B 站用户关注动态"""
    sort_by_key = cls.sort_by_key
    for params in init_params:
        if isinstance(params, dict) or isinstance(params, str):
            instance = cls(params)
        elif isinstance(params, list):
            instance = cls(*params)
        else:
            instance = cls()
        # 确保 source 的元信息在数据库中
        source_info, source_name = instance.get_source_info(), instance.get_table_name()
        data.exist_source_meta(source_info)
        
        collection = data.db[source_name]
        result = collection.find({}, {sort_by_key: 1}).sort(sort_by_key, -1).limit(1)   # 含有 '_id', 
        result = list(result)
        last_update_flag = result[0][sort_by_key] if result else False

        got_new = False
        if not last_update_flag:
            # 若是第一次，数据库中没有数据
            got_new = True
            article_source = instance.first_add()
        else:
            article_source = instance.get_new(last_update_flag)
        
        async for a in article_source:
            # 每篇文章整合成一个文档，存入相应集合
            one_article_etc = {
                "article_infomation": a, 
                sort_by_key: a[sort_by_key]
            }
            data.store2database(source_name, one_article_etc)
            logger.info(f"{source_name} have new article: {a['article_name']}")
            got_new = True
        
        # 生成 RSS 并保存到目录
        if got_new:
            generate_rss(collection, sort_by_key, config.rss_dir, data.db[config.source_meta])
        else:
            logger.info(f"{source_name} didn't update")


async def monitor_website(config, data, plugins):
    """控制总流程： 解析，整合，保存，生成 RSS"""
    logger.info("***Start all tasks***")

    tasks = chain(
        (chapter_mode(config, data, config.cls_init_params[cls.__name__], cls) for cls in plugins["chapter_mode"]),
        (one_website(config, data, cls) for cls in plugins["static"])
    )
    await asyncio.gather(*tasks)

    logger.info("***Have finished all tasks***")


async def main():
    from preprocess import config, data, plugins

    # 开发环境下，每次都把集合清空
    if not config.is_production:
        logger.info("Clear All Collections")
        data._clear_db()
    
    await monitor_website(config, data, plugins)


if __name__ == "__main__":
    def handler(sig, frame):
        # 退出前清理环境
        exit(0)
    signal.signal(signal.SIGINT, handler)

    asyncio.run(main())
