

from collections import defaultdict

scraper_class_table_name_prefix = (
    ("bilibili_up_", "B站UP主动态"),
    ("youtube_channel_", "Youtube Channel"),
    ("fanqie_book_", "番茄小说"),
    ("mangacopy_book_", "拷貝漫畫"),
    ("zhihu_user_", "知乎用户动态"),
    ("twitter_user_", "Twitter"),
)

def sort_rss_list(rss_list: list[tuple[str, str]]) -> list[tuple[str, tuple[str, str]]]:
    sorted_rss = defaultdict(list)
    for rss in rss_list:
        for prefix, group_name in scraper_class_table_name_prefix:
            if rss[0].startswith(prefix):
                sorted_rss[group_name].append(rss)
                break
        else:
            sorted_rss["singleton"].append(rss)

    for new_rss_list in sorted_rss.values():
        new_rss_list.sort(key=lambda x: x[1])
    sorted_rss = sorted(sorted_rss.items())
    return sorted_rss # type: ignore
