from datetime import datetime
import logging
import signal
import asyncio

from generate_rss import generate_rss

logger = logging.getLogger("main")


async def one_website(config, data, source_name, cls):
    """对某个网站的文章进行更新"""
    # 确保 source 的元信息在数据库中
    source_info = cls.source_info
    data.exist_source_meta(source_info)
    
    collection = data.db[source_name]
    result = collection.find({}, {'pub_time': 1}).sort('pub_time', -1).limit(1)   # 含有 '_id', 
    result = list(result)
    last_update_time = result[0]["pub_time"] if result else datetime.fromtimestamp(0)
    
    there_is_new_article = False
    async for a in cls.article_newer_than(last_update_time):
        # 每篇文章整合成一个文档，存入相应集合
        one_article_etc = {
            "article_infomation": a, 
            "pub_time": a['pub_time'],
            "rss_time": datetime.fromtimestamp(0)
        }
        data.store2database(source_name, one_article_etc)

        logger.info(f"{source_name} have new article: {a['article_name']}")
        
        there_is_new_article = True
    
    # 生成 RSS 并保存到目录
    if there_is_new_article:
        generate_rss(collection, config.rss_dir, data.db[config.source_meta])
    else:
        logger.info(f"{source_name} didn't update")


async def dynamic_web(config, data, source_name, cls):
    """对某个网站的文章进行更新"""
    instance = cls()
    # 确保 source 的元信息在数据库中
    source_info = cls.source_info
    data.exist_source_meta(source_info)
    
    collection = data.db[source_name]
    result = collection.find({}, {'pub_time': 1}).sort('pub_time', -1).limit(1)   # 含有 '_id', 
    result = list(result)
    last_update_time = result[0]["pub_time"] if result else cls.limit_page or datetime.fromtimestamp(0)

    there_is_new_article = False
    async for a in instance.article_newer_than(last_update_time):
        # 每篇文章整合成一个文档，存入相应集合
        one_article_etc = {
            "article_infomation": a, 
            "pub_time": a['pub_time'],
            "rss_time": datetime.fromtimestamp(0)
        }
        data.store2database(source_name, one_article_etc)

        logger.info(f"{source_name} have new article: {a['article_name']}")
        
        there_is_new_article = True
    
    # 生成 RSS 并保存到目录
    if there_is_new_article:
        generate_rss(collection, config.rss_dir, data.db[config.source_meta])
    else:
        logger.info(f"{source_name} didn't update")


async def chapter_mode(config, data, fanqie_books_id, cls):
    """对番茄的小说进行更新"""
    for title, id in fanqie_books_id:
        instance = cls(title, id)
        # 确保 source 的元信息在数据库中
        source_info = instance.source_info
        data.exist_source_meta(source_info)
        
        source_name = source_info["title"]
        collection = data.db[source_name]
        result = collection.find({}, {'pub_time': 1, 'article_infomation': 1}).sort('pub_time', -1).limit(1)   # 含有 '_id', 
        result = list(result)

        there_is_new_article = False
        if result:
            chapter = result[0]["article_infomation"]["chapter_number"]
            async for a in instance.chapter_greater_than(chapter):
                # 每篇文章整合成一个文档，存入相应集合
                one_article_etc = {
                    "article_infomation": a, 
                    "pub_time": a['pub_time'],
                    "rss_time": datetime.fromtimestamp(0)
                }
                data.store2database(source_name, one_article_etc)

                logger.info(f"{source_name} have new article: {a['article_name']}")
                
                there_is_new_article = True
        else:
            async for a in instance.latest_chapter_for():
                # 每篇文章整合成一个文档，存入相应集合
                one_article_etc = {
                    "article_infomation": a, 
                    "pub_time": a['pub_time'],
                    "rss_time": datetime.fromtimestamp(0)
                }
                data.store2database(source_name, one_article_etc)

                logger.info(f"{source_name} have new article: {a['article_name']}")
                
                there_is_new_article = True
        
        # 生成 RSS 并保存到目录
        if there_is_new_article:
            generate_rss(collection, config.rss_dir, data.db[config.source_meta])
        else:
            logger.info(f"{source_name} didn't update")


async def monitor_website(config, data, plugins):
    """控制总流程： 解析，整合，保存，生成 RSS"""

    await asyncio.gather(*(chapter_mode(config, data, config.fanqie_books_id, cls) for _, cls in plugins["chapter_mode"].items()))
    await asyncio.gather(*(one_website(config, data, source_name, cls) for source_name, cls in plugins["static"].items()))
    await asyncio.gather(*(dynamic_web(config, data, source_name, cls) for source_name, cls in plugins["dynamic"].items()))


async def main():
    import preprocess

    config = preprocess.config
    data = preprocess.data
    plugins = preprocess.plugins

    # 开发环境下，每次都把集合清空
    if not config.is_production:
        data._clear_db()
    
    def handler(sig, frame):
        # 退出前清理环境
        exit(0)
    signal.signal(signal.SIGINT, handler)

    await monitor_website(config, data, plugins)


if __name__ == "__main__":
    asyncio.run(main())
    
    
