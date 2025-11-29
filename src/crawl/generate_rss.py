import re
from datetime import datetime
from zoneinfo import ZoneInfo

from feedgen.feed import FeedGenerator

from configHandle import config
from src.scraper import ArticleDict, SrcMetaDict

UTC = ZoneInfo("UTC")
local_timezone = ZoneInfo(config.timezone)

def clean_xml_string(s: str) -> str:
    # 移除 NULL 字节和控制字符（除了 \t, \n, \r）
    # XML 1.0 允许的控制字符只有 U+0009 (tab), U+000A (LF), U+000D (CR)
    return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', s)


# TODO l10n 时区应该能更改的
def generate_rss(source_info: SrcMetaDict, articles: list[ArticleDict]) -> bytes:
    """构建 rss。根据传入的 articles ，格式化为 RSS 后以 utf-8 字节返回"""
    fg = FeedGenerator()
    fg.title(source_info["name"])
    fg.link(href=source_info["link"], rel='alternate')
    fg.description(source_info["desc"])
    fg.language(source_info["lang"])
    fg.pubDate(datetime.now(tz=local_timezone))
    # 遍历并提取文章信息
    for article in reversed(articles):
        # 添加一篇文章，好像是从顶部往下推着添加的，因此要先放入最老的
        fe = fg.add_entry()
        fe.title(article["title"])
        fe.pubDate(article["pub_time"].replace(tzinfo=UTC).astimezone(local_timezone))
        if url := article["link"]:
            fe.link(href=url)
        if summary := article["summary"]:
            fe.description(clean_xml_string(summary))
        if cover := article.get("image_link"):
            fe.enclosure(cover, 0, 'image/jpeg')
        if content := article.get("content"):
            lines = content.split("\n")
            content = ''.join(f"<p>{line}</p>" if line else "<br />" for line in lines)
            fe.content(content, type="CDATA")

    # 生成 RSS feed
    rss_feed = fg.rss_str(pretty=True)
    return rss_feed
