import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Self

from bs4 import BeautifulSoup

from src.scraper.model import SortKey
from src.scraper.scraper import WebsiteScraper
from src.scraper.scraper_error import CreateButRequestFail, CreateByInvalidParam
from src.scraper.tools import get_response_or_none


class TelegramChannel(WebsiteScraper):
    home_url = "https://t.me/s/{channel_id}"
    page_turning_duration = 5
    table_name_formation = "telegram_channel_{}"

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'cache-control': 'max-age=0',
        'priority': 'u=0, i',
        'referer': '',   # 填充
        'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
    }

    @classmethod
    async def create(cls, channel_id: str) -> Self:
        """
        Args:
            channel_id: 可以在频道的网址中拿到，如 https://t.me/vfly2 中最后一串 vfly2 。约束：不为空且由数字或字母组成。
        """
        if not TelegramChannel.is_valid_channel_id(channel_id):
            raise CreateByInvalidParam()
        channel_url = cls.home_url.format(channel_id=channel_id)
        header = cls.headers.copy()
        header["referer"] = channel_url
        name, desc, soup = await cls._get_channel_info(channel_url, header)
        if name and desc and soup:
            return cls(channel_id, name, desc, channel_url, header, soup)
        raise CreateButRequestFail()

    def __init__(self, *args) -> None:
        super().__init__()
        self.channel_id, self.channel_name, self.channel_desc, self.channel_url, self.header, self.soup = args

    def _source_info(self):
        return {
            "name": f"{self.channel_name} - Telegram",
            "link": f"https://t.me/{self.channel_id}",
            "desc": self.channel_desc,
            "lang": "zh-CN",
            "key4sort": SortKey.PUB_TIME,
            "table_name": TelegramChannel.table_name_formation.format(self.channel_id),
        }

    @classmethod
    async def _parse(cls, flags, channel_name, channel_url: str, soup: BeautifulSoup, header: dict) -> AsyncGenerator[dict, None]:  # noqa: ARG003, C901
        cls._logger.info("%s start to parse", channel_name)
        while True:
            articles = soup.find_all('div', class_='tgme_widget_message_wrap js-widget_message_wrap')
            if not articles:
                cls._logger.info("%s unexpected content 1", channel_name)
                return
            for a in reversed(articles):
                content = a.find('div', class_="tgme_widget_message_text js-message_text")
                if not content:
                    cls._logger.info("%s unexpected content 2", channel_name)
                    continue
                link_tag = content.find('a', href=True)
                if not link_tag:
                    cls._logger.info("%s unexpected content 3", channel_name)
                    continue
                article_url = link_tag['href']
                title = link_tag.get_text(strip=True)
                summary = ""

                footer = a.find('div', class_="tgme_widget_message_footer")
                if not footer:
                    cls._logger.info("%s unexpected content 4", channel_name)
                    continue
                info = footer.find('div', class_="tgme_widget_message_info")
                if not info:
                    cls._logger.info("%s unexpected content 5", channel_name)
                    continue
                time_tag = info.find('time', datetime=True)
                if not time_tag:
                    cls._logger.info("%s unexpected content 6", channel_name)
                    continue
                iso_time = time_tag['datetime']
                time_obj = datetime.fromisoformat(iso_time) # type: ignore

                preview = a.find('a', class_="tgme_widget_message_link_preview")
                if preview:
                    preview_t = preview.find('div', class_="link_preview_title")
                    preview_t = preview_t.text if preview_t else ""
                    preview_d = preview.find('div', class_="link_preview_description")
                    preview_d = preview_d.text if preview_d else ""
                    summary += "\n" + preview_t + "\n" + preview_d

                article = {
                    "title": title,
                    "summary": summary,
                    "link": article_url,
                    "image_link": "http://example.com",
                    "pub_time": time_obj
                }

                yield article
            cur_msg_link_tag = a.find('a', class_="tgme_widget_message_date")
            if not cur_msg_link_tag:
                break
            await asyncio.sleep(cls.page_turning_duration)

            cur_msg_link = cur_msg_link_tag['href']
            cur_msg_id = cur_msg_link.rsplit("/", maxsplit=1)[1] # type: ignore
            pre_msgs_link = f"{channel_url}?before={cur_msg_id}"
            response = await get_response_or_none(pre_msgs_link, header)
            if response and response.status_code == 200:
                soup = BeautifulSoup(response.text, features="lxml")
            else:
                raise CreateButRequestFail()

    def _custom_parameter_of_parse(self) -> list:
        return [self.channel_name, self.channel_url, self.soup, self.header]

    @classmethod
    async def _get_channel_info(cls, channel_url: str, header: dict) -> tuple[str, str, BeautifulSoup | None]:
        response = await get_response_or_none(channel_url, header)
        if response and response.status_code == 200:
            soup = BeautifulSoup(response.text, features="lxml")
            right_column = soup.find('section', class_='tgme_right_column')
            if right_column:
                title_div = right_column.find('div', class_='tgme_channel_info_header_title')
                channel_name = title_div.get_text(strip=True) if title_div else "未找到标题"
                desc_div = right_column.find('div', class_='tgme_channel_info_description')
                channel_desc = desc_div.get_text(strip=True) if desc_div else "未找到描述"
                return channel_name, channel_desc, soup
        return "", "", None

    @staticmethod
    def is_valid_channel_id(s: str) -> bool:
        return isinstance(s, str) and len(s) > 0 and all(c.isalnum() or c in "-_" for c in s)
