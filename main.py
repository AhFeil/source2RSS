from datetime import datetime
import logging
import signal
import asyncio

from generate_rss import generate_rss

logger = logging.getLogger("main")


async def monitor_website(config, data, plugins):
    """控制总流程： 解析，整合，保存，生成 RSS"""

    # 确保 source 的元信息在数据库中
    for source_name, cls in plugins.items():
        source_info = cls.source_info
        data.exist_source_meta(source_info)

    # 更新文章
    for source_name, cls in plugins.items():
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
    
    
