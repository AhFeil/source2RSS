import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator

from bs4 import BeautifulSoup
from .example import WebsiteScraper, FailtoGet

import httpx


class CareerTsinghua(WebsiteScraper):
    title = "清华大学学生职业发展指导中心-招聘信息"
    home_url = "https://career.cic.tsinghua.edu.cn/xsglxt/f/jyxt/anony/xxfb"
    domain_url = "https://career.cic.tsinghua.edu.cn"
    page_turning_duration = 10
    key4sort = "time4sort"

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'cache-control': 'max-age=0',
        'content-type': 'application/x-www-form-urlencoded',
        'cookie': 'Secure; JSESSIONID=abcTXGcf53YtA--2ynRcz; serverid=1425456',
        'origin': 'https://career.cic.tsinghua.edu.cn',
        'priority': 'u=0, i',
        'referer': 'https://career.cic.tsinghua.edu.cn/xsglxt/f/jyxt/anony/xxfb',
        'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Microsoft Edge";v="126"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
    }

    def _source_info(self):
        source_info = {
            "name": self.__class__.title,
            "link": self.__class__.home_url,
            "desc": "清华大学学生职业发展指导中心的招聘信息，本源不会显示置顶文章",
            "lang": "zh-CN",
            "key4sort": self.__class__.key4sort
        }
        return source_info

    @classmethod
    async def _parse(cls, logger, start_page: int=1) -> AsyncGenerator[dict, None]:
        """给起始页码，跳过红色字（color:#ff0000 置顶的）yield 一篇一篇惰性返回，直到最后一页最后一篇"""
        data_raw = {
            'flag': '',
            'type': '',
            'pgno': '1',
            'zwmc': '',
            'dwmc': '',
            'gzdqmc': '',
            'dwxzdm': '',
            'dwhydm': '',
            'zwlb': '',
            'zwxz': '',
            'xlyq': '',
            'zwbqmc': '',
        }

        while True:
            data_raw['pgno'] = str(start_page)
            logger.info(f"{cls.title} start to parse page {start_page}")
            response = await cls._request(cls.home_url, data_raw)
            if response is None:
                return
            soup = BeautifulSoup(response.text, features="lxml")

            # Find all list items under the ul with id 'todayList'
            all_articles = soup.find_all('ul', id='todayList')[0].find_all('li')
            if not all_articles:
                return
            
            time_off = iter(range(50))   # 由于网站时间精度只到天，排序时，同一天的会按照标题输出，而不是原始顺序，增加修正时间 time4sort 用于排序
            for article in all_articles:
                style = article.find('a')['style']
                color = style.split(':')[1].split(';')[0]
                if color == "#ff0000":
                    # 跳过置顶的文章
                    continue

                title = article.find('a').text.strip()
                article_url = cls.domain_url + article.find('a').get('ahref')
                
                time = article.find('span').text.strip()
                time_obj = datetime.strptime(time, "%Y-%m-%d")
                mend_time = time_obj - timedelta(minutes=int(next(time_off)))

                article = {
                    "title": title,
                    "summary": title,
                    "link": article_url,
                    "image_link": "https://example.com/",
                    "pub_time": time_obj,
                    "time4sort": mend_time
                }

                yield article

            start_page += 1
            await asyncio.sleep(cls.page_turning_duration)

    @classmethod
    async def _request(cls, url: str, data_raw: dict) -> httpx.Response | None:
        # 设置超时时间为60秒
        timeout = httpx.Timeout(60.0, read=60.0)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.post(url=url, headers=cls.headers, data=data_raw, timeout=timeout)
            except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout):
                raise FailtoGet
        return response
