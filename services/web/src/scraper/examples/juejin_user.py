import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Self

from bs4 import BeautifulSoup

from src.scraper.model import SortKey
from src.scraper.scraper import WebsiteScraper
from src.scraper.scraper_error import (
    CreateButRequestFail,
    CreateByInvalidParam,
)
from src.scraper.tools import AsyncBrowserManager


class JuejinUser(WebsiteScraper):
    """掘金用户文章抓取器"""
    readable_name = "掘金用户文章"
    home_url = "https://juejin.cn"
    page_turning_duration = 30
    table_name_formation = "juejin_user_{}"

    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }

    @classmethod
    async def create(cls, user_id: int | str) -> Self:
        """
        Args:
            user_id: 掘金用户 ID，如 3320949647350765
        """
        if not cls.is_valid_user_id(user_id):
            raise CreateByInvalidParam()
        profile_url = f"{cls.home_url}/user/{user_id}"
        user_info = await cls.get_user_info(user_id, profile_url)
        if user_info is None:
            raise CreateButRequestFail()
        return cls(user_id, user_info)

    def __init__(self, *args) -> None:
        super().__init__()
        self.user_id, self.user_info = args

    def _source_info(self):
        name = f"掘金用户「{self.user_info['name']}」的文章"
        return {
            "name": name,
            "link": f"{self.home_url}/user/{self.user_id}/posts",
            "desc": f"掘金创作者 {self.user_info['name']} 的文章列表",
            "lang": "zh-CN",
            "key4sort": SortKey.PUB_TIME,
            "table_name": JuejinUser.table_name_formation.format(self.user_id),
        }

    @property
    def max_wait_time(self):
        return JuejinUser.page_turning_duration * 3

    @classmethod
    async def get_user_info(cls, user_id: int | str, profile_url: str):
        """获取用户信息"""
        id_ = JuejinUser.table_name_formation.format(user_id)

        html_content = await AsyncBrowserManager.get_html_or_none(id_, profile_url, cls.headers["User-Agent"])
        if html_content is None:
            return None
        soup = BeautifulSoup(html_content, features="lxml")

        # 从 meta 标签获取用户名
        name_tag = soup.find('meta', itemprop='name')
        user_name = name_tag['content'] if name_tag else f"用户{user_id}"

        # 获取头像
        avatar_tag = soup.find('meta', itemprop='image')
        avatar_url = avatar_tag['content'] if avatar_tag else ""

        return {
            "name": user_name,
            "avatar": avatar_url,
        }

    @classmethod
    async def _parse(cls, _flags, user_id) -> AsyncGenerator[dict, None]:
        posts_url = f"{cls.home_url}/user/{user_id}/posts"
        id_ = JuejinUser.table_name_formation.format(user_id)
        cls._logger.info("%s start to parse", id_)

        # 使用同一个浏览器上下文完成所有操作，避免重复启动浏览器
        async with AsyncBrowserManager(id_, cls.headers["User-Agent"]) as context:
            # 1. 获取文章列表页面
            page = await context.new_page()
            try:
                await page.goto(posts_url, timeout=60000, wait_until='networkidle')
            except Exception as e:
                cls._logger.warning("Failed to fetch posts page: %s", e)
                return

            html_content = await page.content()
            soup = BeautifulSoup(html_content, features="lxml")

            # 查找文章列表
            entry_list = soup.find('div', class_='entry-list')
            if not entry_list:
                cls._logger.warning("No entry-list found")
                return

            # 2. 解析所有文章基本信息
            entries_data = []
            for entry in entry_list.find_all('li', class_='item'):
                article_data = cls._parse_entry(entry)
                if article_data:
                    entries_data.append(article_data)

            # 3. 依次访问每篇文章获取精确时间（复用同一个 context）
            for article_data in entries_data:
                pub_time = await cls._fetch_article_time(page, article_data["link"])
                article_data["pub_time"] = pub_time

                yield article_data
                await asyncio.sleep(cls.page_turning_duration)

    @classmethod
    def _parse_entry(cls, entry):
        """解析单个文章条目（不包含精确时间）"""
        try:
            # 查找内部的 div（data-entry-id 在 class="entry" 的 div 上）
            entry_div = entry.find('div', class_='entry')
            if not entry_div:
                return None

            # 获取文章 ID
            article_id = entry_div.get('data-entry-id')
            if not article_id:
                return None

            # 获取标题
            title_elem = entry_div.find('a', class_='title')
            title = title_elem.get_text(strip=True) if title_elem else ""
            article_url = f"{cls.home_url}/post/{article_id}" if article_id else ""

            # 获取摘要
            abstract_elem = entry_div.find('div', class_='abstract')
            summary = abstract_elem.get_text(strip=True) if abstract_elem else ""

            return {
                "title": title,
                "summary": summary,
                "link": article_url,
                "article_id": article_id,
            }
        except Exception as e:
            cls._logger.warning("Failed to parse entry: %s", e)
            return None

    @classmethod
    async def _fetch_article_time(cls, page, article_url: str) -> datetime:
        """在已有 page 上访问文章页面获取精确发布时间"""
        try:
            await page.goto(article_url, timeout=60000, wait_until='networkidle')
            html_content = await page.content()
            soup = BeautifulSoup(html_content, features="lxml")

            # 从 meta-box 中获取时间
            meta_info = soup.find('div', class_='meta-box')
            if not meta_info:
                return datetime.now()

            time_elem = meta_info.find('time', class_="time")
            if not time_elem:
                return datetime.now()

            time_str = time_elem.get("datetime", "")
            if not time_str:
                return datetime.now()

            try:
                # 时间格式如 "2025-11-25T10:30:00.000Z"
                time_obj = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ") # type: ignore
                return time_obj
            except ValueError:
                try:
                    time_obj = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ") # type: ignore
                    return time_obj
                except ValueError:
                    return datetime.now()
        except Exception as e:
            cls._logger.warning("Failed to fetch article time: %s", e)
            return datetime.now()

    def _custom_parameter_of_parse(self):
        return (self.user_id,)

    @staticmethod
    def is_valid_user_id(s: int | str) -> bool:
        return (isinstance(s, int) and s > 10000) or isinstance(s, str) and 4 <= len(s) <= 25 and all(c.isdigit() for c in s)
