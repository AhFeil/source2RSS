from datetime import datetime, timezone, timedelta

from feedgen.feed import FeedGenerator

from src.website_scraper import SrcMetaDict, ArticleDict


def generate_rss(source_info: SrcMetaDict, articles: list[ArticleDict]) -> bytes:
    """构建 rss。根据传入的 articles ，格式化为 RSS 后以 utf-8 字节返回"""
    zone = timezone(timedelta(hours=8))

    fg = FeedGenerator()
    fg.title(source_info["name"])
    fg.link(href=source_info["link"], rel='alternate')
    fg.description(source_info["desc"])
    fg.language(source_info["lang"])
    fg.pubDate(datetime.now(tz=zone))
    # 遍历并提取文章信息
    for article in reversed(articles):
        title = article["title"]
        url = article["link"]
        pub_date = article["pub_time"].astimezone(zone)
        summary = article["summary"]

        # 添加一篇文章，好像是从顶部往下推着添加的，因此要先放入最老的
        fe = fg.add_entry()
        fe.title(title)
        fe.link(href=url)
        fe.pubDate(pub_date)
        fe.description(summary)
        if cover := article.get("image_link"):
            fe.enclosure(cover, 0, 'image/jpeg')
        if content := article.get("content"):
            lines = content.split("\n")
            content = ''.join(f"<p>{line}</p>" if line else "<br />" for line in lines)
            fe.content(content, type="CDATA")

    # 生成 RSS feed
    rss_feed = fg.rss_str(pretty=True)
    return rss_feed
