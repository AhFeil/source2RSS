import asyncio
from typing import AsyncGenerator, Any

from .example import WebsiteScraper
from utils.imap_client import ImapMailBox


class NewsLetter(WebsiteScraper):
    title = "NewsLetter"
    home_url = "http://example.com"
    page_turning_duration = 5
    key4sort = "pub_time"

    def __init__(self, from_email: str, newsletter_name: str, host, port, username, password, ssl=True) -> None:
        super().__init__()
        self.from_email = from_email
        self.newsletter_name = newsletter_name
        self.mailbox = ImapMailBox(host, port, username, password, ssl)

    @property
    def source_info(self):
        return {
            "title": f"NewsLetter of {self.newsletter_name}",
            "link": self.__class__.home_url,
            "description": f"NewsLetter of {self.newsletter_name}",
            "language": "En",
            "key4sort": self.__class__.key4sort}

    @classmethod
    async def parse(cls, logger, from_email, mailbox: ImapMailBox) -> AsyncGenerator[dict, Any]:
        logger.info(f"{cls.title} start to parse email {from_email}")
        with mailbox:
            for mail in mailbox.get_mails():
                # 当 from_email 不为空时，必须是 from_email 发来的邮件才会处理
                if from_email and mail.from_addr != from_email:
                    continue
                article = {
                    "article_name": mail.subject,
                    "summary": mail.plain,
                    "article_url": "http://example.com",
                    "image_link": "http://example.com",
                    "pub_time": mail.date.replace(tzinfo=None)   # 去除时区信息，否则无法对比
                }
                yield article
                await asyncio.sleep(cls.page_turning_duration)

    def custom_parameter_of_parse(self) -> list:
        return [self.from_email, self.mailbox]


import api._v1
api._v1.register_c(NewsLetter)


async def test():
    w = NewsLetter("", "Test", host='imap.gmail.com', port=993, username="", password="")
    print(w.source_info)
    print(w.table_name)
    async for a in w.first_add():
        print(a)
    print("----------")
    async for a in w.get_new(datetime(2025, 1, 1)):
        print(a)
    print("----------")


if __name__ == "__main__":
    asyncio.run(test())
    # python -m website_scraper.newsletter
