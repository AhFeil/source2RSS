"""联合早报板块抓取器

支持两个字符串参数定位板块：
- category1: 第一级分类，如 "news", "realtime", "finance"
- category2: 第二级分类，如 "china", "world", "sports"

例如：
- news/china: https://www.zaobao.com/news/china
- realtime/china: https://www.zaobao.com/realtime/china
"""
import asyncio
import json
import re
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
from src.scraper.tools import get_response_or_none
import contextlib


class ZaobaoSection(WebsiteScraper):
    """联合早报板块抓取器"""
    readable_name = "联合早报板块"
    home_url = "https://www.zaobao.com"
    page_turning_duration = 2  # HTTP 请求间隔
    table_name_formation = "zaobao_{}_{}"

    headers = {
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }

    @classmethod
    async def create(cls, category1: str, category2: str) -> Self:
        """
        目前仅能在中国大陆网络下抓取。

        Args:
            category1: 第一级分类，如 "news", "realtime", "finance"
            category2: 第二级分类，如 "china", "world", "sports"
        """
        if not cls.is_valid_category(category1) or not cls.is_valid_category(category2):
            raise CreateByInvalidParam()

        section_url = f"{cls.home_url}/{category1}/{category2}"
        section_name = await cls.get_section_name(category1, category2, section_url)
        if section_name is None:
            raise CreateButRequestFail()

        return cls(category1, category2, section_url, section_name)

    def __init__(self, *args) -> None:
        super().__init__()
        self.category1, self.category2, self.section_url, self.section_name = args

    def _source_info(self):
        name = f"联合早报 {self.section_name}"
        return {
            "name": name,
            "link": self.section_url,
            "desc": f"联合早报 {self.section_name} 板块的文章",
            "lang": "zh-CN",
            "key4sort": SortKey.PUB_TIME,
            "table_name": ZaobaoSection.table_name_formation.format(self.category1, self.category2),
        }

    @property
    def max_wait_time(self):
        return ZaobaoSection.page_turning_duration * 30

    @classmethod
    async def get_section_name(cls, category1: str, category2: str, section_url: str) -> str | None:
        """获取板块名称"""
        response = await get_response_or_none(section_url, headers=cls.headers, timeout=30)
        if response is None:
            return None

        soup = BeautifulSoup(response.text, features="lxml")

        # 尝试从页面标题获取板块名称
        title = soup.find('title')
        if title:
            # 标题格式如 "中国新闻 | 联合早报网"
            text = title.get_text(strip=True)
            if '|' in text:
                return text.split('|')[0].strip()
            # 尝试匹配 "xxx新闻" 格式
            match = re.search(r'^(.+?新闻)', text)
            if match:
                return match.group(1)

        # 备选：从 meta description 获取
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            # 内容格式如 "中国新闻 -《联合早报》是..."
            content = meta_desc['content']
            if ' - ' in content:
                return content.split(' - ')[0].strip()

        return f"{category1}/{category2}"

    @classmethod
    async def _parse(cls, flags, category1, category2, section_url) -> AsyncGenerator[dict, None]:
        """按从新到旧解析文章"""
        id_ = cls.table_name_formation.format(category1, category2)
        cls._logger.info("%s start to parse", id_)

        # 1. 获取板块页面
        response = await get_response_or_none(section_url, headers=cls.headers, timeout=30)
        if response is None:
            cls._logger.warning("Failed to fetch section page")
            return

        soup = BeautifulSoup(response.text, features="lxml")

        # 2. 解析所有文章链接
        articles_data = cls._extract_articles_from_page(soup, section_url)

        if not articles_data:
            cls._logger.warning("No articles found on page")
            return

        # 3. 依次访问每篇文章获取精确时间和摘要
        for article_data in articles_data:
            details = await cls._fetch_article_details(article_data["link"])
            article_data["pub_time"] = details["pub_time"]
            article_data["summary"] = details["summary"]
            yield article_data
            await asyncio.sleep(cls.page_turning_duration)

    @classmethod
    def _extract_articles_from_page(cls, soup: BeautifulSoup, section_url: str) -> list[dict]:
        """从页面中提取文章信息（不含精确时间）"""
        articles = []

        # 从 section_url 解析出目标板块
        # section_url 格式: https://www.zaobao.com/category1/category2
        match = re.match(rf'{re.escape(cls.home_url)}/([^/]+)/([^/]+)', section_url)
        if not match:
            return []
        target_cat1, target_cat2 = match.group(1), match.group(2)

        # 查找本板块的文章链接（使用 article-link 类，排除热门区域的 hotnews_* 类）
        article_links = soup.find_all('a', class_='article-link')

        for link in article_links:
            href = link.get('href', '')
            title = link.get('title', '') or link.get_text(strip=True)

            # 跳过空标题
            if not title:
                continue

            # 确保链接是完整URL
            if href.startswith('/'):
                full_url = f"{cls.home_url}{href}"
            elif href.startswith('http'):
                full_url = href
            else:
                continue

            # 只保留本板块的文章
            # 链接格式: /category1/category2/story...
            match = re.match(rf'/([^/]+)/([^/]+)/story', href)
            if match:
                cat1, cat2 = match.group(1), match.group(2)
                # 必须完全匹配目标板块
                if cat1 == target_cat1 and cat2 == target_cat2:
                    articles.append({
                        "title": title,
                        "link": full_url,
                    })

        # 去重（基于链接）
        seen = set()
        unique_articles = []
        for a in articles:
            if a["link"] not in seen:
                seen.add(a["link"])
                unique_articles.append(a)

        return unique_articles

    @classmethod
    async def _fetch_article_details(cls, article_url: str) -> dict:
        """访问文章页面获取精确发布时间和摘要"""
        response = await get_response_or_none(article_url, headers=cls.headers, timeout=30)
        if response is None:
            return {"pub_time": datetime.now(), "summary": ""}

        html = response.text
        pub_time = datetime.now()
        summary = ""

        # 方法1: 从 JSON-LD 获取时间和摘要
        match = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                date_str = data.get('datePublished') or data.get('dateCreated')
                if date_str:
                    pub_time = cls._parse_date(date_str)
                # 从 JSON-LD 获取摘要
                summary = data.get('description', '') or data.get('articleBody', '')[:200]
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # 方法2: 从 script 中的 gaPushParams 获取时间
        match = re.search(r'"pubdate":"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"', html)
        if match:
            with contextlib.suppress(ValueError):
                pub_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")

        # 方法3: 从 meta description 获取摘要
        if not summary:
            meta_desc = BeautifulSoup(html, features="lxml").find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                summary = meta_desc['content'][:200]

        return {"pub_time": pub_time, "summary": summary}

    @classmethod
    def _parse_date(cls, date_str: str) -> datetime:
        """解析日期字符串"""
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00').replace('+08:00', '+08:00'))
        except ValueError:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return datetime.now()

    def _custom_parameter_of_parse(self) -> tuple:
        return (self.category1, self.category2, self.section_url)

    @staticmethod
    def is_valid_category(s: str) -> bool:
        """验证分类参数"""
        return isinstance(s, str) and 1 <= len(s) <= 20 and all(c.isalnum() or c == '-' for c in s)
