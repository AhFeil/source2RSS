import asyncio
from typing import AsyncGenerator

from .example import WebsiteScraper
from utils.imap_client import ImapMailBox


class NewsLetter(WebsiteScraper):
    title = "NewsLetter"
    page_turning_duration = 5
    key4sort = "pub_time"

    def __init__(self, froms: dict[str, str], host, port, username, password, ssl=True) -> None:
        super().__init__()
        self.from_email = froms.get("from_email", "")
        self.website = froms.get("website", "http://example.com")
        self.newsletter_name = froms.get("name", "NameLack")
        self.desc = froms.get("desc", "DescriptionLack")
        self.mailbox = ImapMailBox(host, port, username, password, ssl)

    def _source_info(self):
        return {
            "title": f"NewsLetter of {self.newsletter_name}",
            "link": self.website,
            "desc": self.desc or "DescriptionLack",   # 不能为空，否则无法生成 RSS
            "lang": "En",
            "key4sort": self.__class__.key4sort}

    @classmethod
    async def _parse(cls, logger, from_email, website, mailbox: ImapMailBox) -> AsyncGenerator[dict, None]:
        logger.info(f"{cls.title} start to parse email {from_email}")
        with mailbox:
            for mail in mailbox.get_mails("ALL"):
                # 当 from_email 不为空时，必须是 from_email 发来的邮件才会处理
                if from_email and mail.from_addr != from_email:
                    continue
                article = {
                    "title": mail.subject,
                    "summary": mail.plain or mail.html,
                    "link": website,
                    "image_link": "http://example.com",
                    "pub_time": mail.date.replace(tzinfo=None)   # 去除时区信息，否则无法对比
                }
                yield article
                await asyncio.sleep(cls.page_turning_duration)

    def _custom_parameter_of_parse(self) -> list:
        return [self.from_email, self.website, self.mailbox]
