from typing import AsyncGenerator, Self

from src.website_scraper.scraper import WebsiteScraper, CreateByInvalidParam


class Representative(WebsiteScraper):
    title = "no body"
    home_url = ""

    @classmethod
    async def create(cls, source: dict, articles: list[dict]) -> Self:
        # todo 对 articles 每项进行校验
        if source and articles:
            return cls(source, articles)
        raise CreateByInvalidParam

    def __init__(self, *args) -> None:
        super().__init__()
        self.source, self.articles = args

    def _source_info(self):
        return self.source

    @classmethod
    async def _parse(cls, flags, articles) -> AsyncGenerator[dict, None]:
        for a in articles:
            yield a

    def _custom_parameter_of_parse(self) -> tuple:
        return (self.articles, )
