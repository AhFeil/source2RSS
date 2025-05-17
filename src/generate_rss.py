from datetime import datetime, timezone, timedelta

from feedgen.feed import FeedGenerator


def generate_rss(source_info: dict, articles: list[dict]) -> bytes:
    """构建 rss。根据传入的 articles ，格式化为 RSS 后以 utf-8 字节返回"""
    zone = timezone(timedelta(hours=8))

    fg = FeedGenerator()
    fg.title(source_info["title"])
    fg.link(href=source_info["link"], rel='alternate')
    fg.description(source_info["description"])
    fg.language(source_info["language"])
    fg.pubDate(datetime.now(tz=zone))
    # 遍历并提取文章信息
    for doc in reversed(articles):
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

        if content := article.get("content"):
            lines = content.split("\n")
            content = ''.join(f"<p>{l}</p>" if l else "<br />" for l in lines)
            fe.content(content, type="CDATA")

    # 生成 RSS feed
    rss_feed = fg.rss_str(pretty=True)
    return rss_feed

def generate_rss_from_collection(source_info, collection: str):
    """从 collection 中取出前 10 条最新的消息，调用 generate_rss 生成 RSS 文件"""
    key4sort = source_info["key4sort"]
    try:
        result = collection.find({}, {'article_infomation': 1}).sort(key4sort, -1).limit(50)   # 含有 '_id', 由新到旧、由大到小排序
    except Exception as e:
        print("Unpredictable Exception when get articles from collection")
    # result 的结构是 [{ "_id":, "article_infomation": {} },    ]
    else:
        return generate_rss(source_info, list(result))
