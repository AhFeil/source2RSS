from typing import AsyncGenerator, Self

from src.website_scraper.scraper import WebsiteScraper, CreateByInvalidParam


class Representative(WebsiteScraper):
    title = "no body"
    home_url = ""
    key4sort = "pub_time"   # todo

    @classmethod
    async def create(cls, source_name: str, articles: list[dict]) -> Self:
        # 对 articles 每项进行校验
        if source_name and articles:
            return cls(source_name, articles)
        raise CreateByInvalidParam

    def __init__(self, *args) -> None:
        super().__init__()
        self.source_name, self.articles = args

    def _source_info(self):
        return {
            "name": self.source_name,
            "link": "http://rss.vfly2.com/",
            "desc": "no body",
            "lang": "zh-CN",
            "key4sort": "pub_time"
        }

    @classmethod
    async def _parse(cls, flags, articles) -> AsyncGenerator[dict, None]:
        for a in articles:
            yield a

    def _custom_parameter_of_parse(self) -> tuple:
        return (self.articles, )
