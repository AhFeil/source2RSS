from datetime import datetime
import json
import signal
import asyncio

from generate_rss import generate_rss
from website_scraper.bentoml import BentoMLBlog



async def main(config, data):
    """控制总流程： 解析，整合，保存，生成 RSS"""
    name = "BentoML Blog"
    collection = data.db["BentoML Blog"]
    result = collection.find({}, {'pub_time': 1}).sort('pub_time', -1).limit(1)   # 含有 '_id', 
    result = list(result)
    rss_time = datetime.fromtimestamp(0)

    last_update_time = result[0]["pub_time"] if result else datetime.fromtimestamp(0)
    async for a in BentoMLBlog.article_newer_than(last_update_time):
        # 每篇文章整合成一个文档，存入相应集合
        one_article_etc = {
            "article_infomation": a, 
            "pub_time": a['pub_time'],
            "rss_time": rss_time
        }
        data.store2database(name, one_article_etc)

        print(f"article name: {a['article_name']}")
        break
    print("-----\n")
    
    # 生成 RSS 并保存到目录
    generate_rss(collection, config.rss_dir, data.db[config.source_meta])


if __name__ == "__main__":
    import preprocess

    config = preprocess.config
    data = preprocess.data
    # 开发环境下，每次都把集合清空
    # if not config.is_production:
    #     data._clear_db()
    
    def handler(sig, frame):
        # 退出前清理环境
        exit(0)

    signal.signal(signal.SIGINT, handler)



    source_info = {
        "title": "BentoML Blog",
        "link": "https://www.bentoml.com/blog",
        "description": "This is BentoML Blog",
        "language": "En"
    }
    
    data.add_source2meta(source_info)
    
    asyncio.run(main(config, data))
    
    
