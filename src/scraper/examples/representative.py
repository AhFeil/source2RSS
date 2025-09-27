from collections.abc import AsyncGenerator
from typing import Self

from src.scraper.scraper import WebsiteScraper
from src.scraper.scraper_error import CreateByInvalidParam


class Representative(WebsiteScraper):
    home_url = ""

    @classmethod
    async def create(cls, source: dict, articles: list[dict]) -> Self:
        """
        Args:
            source: 源的元信息字典
            articles: 要在源中发布的文章列表
        """
        if source and articles:
            return cls(source, articles)
        raise CreateByInvalidParam()

    def __init__(self, *args) -> None:
        super().__init__()
        self.source, self.articles = args

    def _source_info(self):
        return self.source

    @classmethod
    async def _parse(cls, flags, articles) -> AsyncGenerator[dict, None]: # noqa: ARG003
        for a in articles:
            yield a

    def _custom_parameter_of_parse(self) -> tuple:
        return (self.articles, )
