"""主动请求某个源的 RSS ，会触发抓取过程并返回结果"""
import logging
from datetime import datetime
from typing import Annotated
from functools import wraps

from cachetools import TTLCache
from fastapi import APIRouter, Query, HTTPException, status, Depends
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasicCredentials

from src.website_scraper import WebsiteScraper
from src.crawler import process_crawl_flow_of_one, CrawlInitError
from preproc import Plugins, data, config
from .security import security, UserRegistry
from .get_rss import get_saved_rss

logger = logging.getLogger("query_rss")

router = APIRouter(
    prefix="/query_rss",
    tags=["query_rss"],
)

cache=TTLCache(maxsize=config.query_cache_maxsize, ttl=config.query_cache_ttl_s)

def async_cached(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 根据传入的参数生成唯一的 key
        cache_key = (args, frozenset(kwargs.items()))
        if cache_key in cache:
            return cache[cache_key]
        result = await func(*args, **kwargs)
        cache[cache_key] = result
        return result
    return wrapper

async def no_cache_flow(cls_id: str, cls: WebsiteScraper, q: tuple) -> str:
    try:
        res = await process_crawl_flow_of_one(data, cls, [q], config.get_amount(cls_id))
        return res[0]
    except CrawlInitError as e:
        raise HTTPException(status_code=e.code, detail=str(e))

@async_cached
async def cache_flow(cls_id: str, cls: WebsiteScraper, q: tuple) -> str:
    return await no_cache_flow(cls_id, cls, q)

@router.get("/{cls_id}/", response_class=PlainTextResponse)
async def query_rss(cls_id: str, q: Annotated[list[str], Query()] = [],
                    credentials: HTTPBasicCredentials = Depends(security)):
    """主动请求，会触发更新，因此需要身份验证。对于普通用户，可以设置缓存防止滥用。获取结果和 get_rss 中的一样，复用即可。"""
    user = UserRegistry.get_valid_user_or_none(credentials.username, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    logger.info(f"{cls_id} get new request of {q}")

    cls: WebsiteScraper | None = Plugins.get_plugin_or_none(cls_id) # type: ignore
    if cls is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scraper Not Found")
    if user.is_administrator and not config.in_bedtime(cls_id, datetime.now().strftime("%H:%M")):
        logger.info("go to no_cache_flow of " + cls_id)
        source_file_name = await no_cache_flow(cls_id, cls, tuple(q))
    else:
        source_file_name = await cache_flow(cls_id, cls, tuple(q))
    return get_saved_rss(source_file_name)
