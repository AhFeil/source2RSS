import os
from datetime import datetime, timezone, timedelta

from feedgen.feed import FeedGenerator


def generate_rss(source_info: dict, articles: list[dict], rss_dir: str):
    """构建 rss。根据传入的 articles ，格式化为 RSS 后以文件形式保存到 rss_dir 下面"""
    zone = timezone(timedelta(hours=8))
    title = source_info["title"]

    fg = FeedGenerator()
    fg.title(source_info["title"])
    fg.link(href=source_info["link"], rel='alternate')
    fg.description(source_info["description"])
    fg.language(source_info["language"])
    fg.pubDate(datetime.now(tz=zone))

    title = title.replace(' ', '_')   # 需要用更完善的库处理
    rss_filename = f"{title}.xml"
    rss_filepath = os.path.join(rss_dir, rss_filename)

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
    # 确保目录存在
    os.makedirs(rss_dir, exist_ok=True)
    # 将生成的 RSS feed 写入文件
    with open(rss_filepath, 'w', encoding='utf-8') as rss_file:
        rss_file.write(rss_feed.decode('utf-8'))


def generate_rss_from_collection(source_info, collection: str, rss_dir):
    """从 collection 中取出前 10 条最新的消息，调用 generate_rss 生成 RSS 文件"""
    # 创建一个时区对象
    key4sort = source_info["key4sort"]
    result = collection.find({}, {'article_infomation': 1}).sort(key4sort, -1).limit(50)   # 含有 '_id', 由新到旧、由大到小排序
    result = list(result)
    # result 的结构是 [{ "_id":, "article_infomation": {} },    ]
    generate_rss(source_info, result, rss_dir)
