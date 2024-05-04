import os
from datetime import datetime, timezone, timedelta
from itertools import groupby

from feedgen.feed import FeedGenerator


def generate_rss(collection, sort_by_key: str, rss_dir, source_meta):
    """构建 rss。根据传入的 collection ，取出前 10 条最新的消息，格式化后以文件形式保存到 rss_dir 下面"""
    # 创建一个时区对象
    zone = timezone(timedelta(hours=8))
    result = collection.find({}, {'article_infomation': 1}).sort(sort_by_key, -1).limit(10)   # 含有 '_id', 
    result = list(result)
    # result 的结构是 [{ "_id":, "article_infomation": {} },    ]
    title = collection.name
    # print(title)

    # 从程序结构说，起码有一个结果，但是万一有什么bug
    try:
        meta_info = source_meta.find_one({"title": title})

        fg = FeedGenerator()
        fg.title(title)
        fg.link(href=meta_info["link"], rel='alternate')
        fg.description(meta_info["description"])
        fg.language(meta_info["language"])
        fg.pubDate(datetime.now(tz=zone))

        title = title.replace(' ', '_')   # 需要用更完善的库处理
        rss_filename = f"{title}.xml"
        rss_filepath = os.path.join(rss_dir, rss_filename)

        # 遍历并提取文章信息
        for doc in reversed(result):
            article = doc["article_infomation"]

            title = article["article_name"]
            url = article["article_url"]
            pub_date = article["pub_time"].astimezone(zone)
            summary = article["summary"]
            cover = article["image_link"]

            # 添加一篇文章，好像是从顶部往下推着添加的，因此要先放入最老的
            fe = fg.add_entry()
            fe.title(title)
            fe.link(href=url)
            fe.pubDate(pub_date)
            fe.description(summary)
            fe.enclosure(cover, 0, 'image/jpeg')

        # 生成 RSS feed
        rss_feed = fg.rss_str(pretty=True)
        # 确保目录存在
        os.makedirs(rss_dir, exist_ok=True)
        # 将生成的 RSS feed 写入文件
        with open(rss_filepath, 'w', encoding='utf-8') as rss_file:
            rss_file.write(rss_feed.decode('utf-8'))

        # 在发布 RSS 之后，更新新文章的 RSS 发布时间
        collection.update_many({"rss_time": datetime.fromtimestamp(0)}, {'$set': {"rss_time": datetime.now()}})
    except IndexError:
        print("IndexError")
    except Exception as e:
        print("generate_rss Exception: ", e)

