"""主动请求某个源的 RSS ，会触发抓取过程并返回结果"""
import logging
from datetime import datetime
from functools import wraps
from typing import Annotated

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse

from preproc import Plugins, config, data
from src.crawl import ClassNameAndParams, start_to_crawl
from src.crawl.crawl_error import CrawlInitError

from .get_rss import select_rss, templates
from .security import User, get_admin_user, get_valid_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/query_rss",
    tags=[__name__],
)


@router.get("/", response_class=HTMLResponse, dependencies=[Depends(get_admin_user)])
async def get_rss_list(request: Request):
    context = {"rss_list": data.rss_cache.get_admin_rss_list(), "is_admin": True}
    return templates.TemplateResponse(request=request, name="rss_list.html", context=context)

@router.get("/{source_name}.xml/", response_class=PlainTextResponse, dependencies=[Depends(get_admin_user)])
async def get_api_rss(source_name: str):
    """查看管理员通过 API 发布的 RSS"""
    rss = data.rss_cache.get_admin_rss_or_None(source_name) or data.rss_cache.get_user_rss_or_None(source_name)
    if rss is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS content is missed in cache")
    return rss.xml


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

async def no_cache_flow(cls_id: str, q: tuple) -> str:
    try:
        res = await start_to_crawl((ClassNameAndParams.create(cls_id, q), ))
        return res[0][0] if res else "error"
    except CrawlInitError as e:
        raise HTTPException(status_code=e.code, detail=str(e))

@async_cached
async def cache_flow(cls_id: str, q: tuple) -> str:
    return await no_cache_flow(cls_id, q)

@router.get("/{cls_id}/", response_class=PlainTextResponse)
async def query_rss(cls_id: str, user: Annotated[User, Depends(get_valid_user)], q: Annotated[list[str], Query()] = []):
    """主动请求，会触发更新，因此需要身份验证。对于普通用户，可以设置缓存防止滥用。获取结果和 get_rss 中的一样，复用即可。"""
    logger.info(f"{cls_id} get new request of {q}")
    if Plugins.get_plugin_or_none(cls_id) is None or cls_id == "Representative":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scraper Not Found")
    if user.is_administrator and not config.in_bedtime(cls_id, datetime.now().strftime("%H:%M")):
        logger.info("go to no_cache_flow of " + cls_id)
        source_name = await no_cache_flow(cls_id, (q, ))
    else:
        source_name = await cache_flow(cls_id, (q, ))

    rss_data = data.rss_cache.get_user_rss_or_None(source_name) or data.rss_cache.get_rss_or_None(source_name)
    return select_rss(rss_data, "xml")
