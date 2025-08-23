"""主动请求某个源的 RSS ，会触发抓取过程并返回结果"""
import logging
from datetime import datetime
from functools import wraps
from typing import Annotated

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from preproc import Plugins, config, data
from src.crawl import ScraperNameAndParams, start_to_crawl
from src.crawl.crawl_error import CrawlInitError
from src.scraper import AccessLevel

from .get_rss import select_rss, templates
from .security import User, UserRegistry, get_valid_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/query_rss",
    tags=[__name__],
)


@router.get("/", response_class=HTMLResponse)
async def get_your_rss_list(request: Request, user: Annotated[User, Depends(get_valid_user)]):
    """已登录用户可以用此查看自己有权限查看的所有源"""
    context = {
        "public_rss_list": data.rss_cache.get_source_list(AccessLevel.PUBLIC),
        "user_rss_list": ((table_name, data.rss_cache.get_source_readable_name(table_name)) for table_name in UserRegistry.get_sources_by_name(user.name)),
        "user_name": user.name,
        "ad_html": config.ad_html
    }
    if user.is_administrator:
        context["rss_list"] = data.rss_cache.get_source_list(AccessLevel.ADMIN, AccessLevel.PUBLIC, (AccessLevel.PRIVATE_USER, ))
    else:
        context["rss_list"] = data.rss_cache.get_source_list(AccessLevel.SHARED_USER, AccessLevel.PUBLIC)

    return templates.TemplateResponse(request=request, name="rss_list.html", context=context)

@router.get("/{source_name}.xml/")
async def get_user_or_upper_rss(source_name: str, user: Annotated[User, Depends(get_valid_user)]):
    """已登录用户可以用此访问有权限查看的所有源"""
    if user.is_administrator:
        rss_data = data.rss_cache.get_source_or_None(source_name, AccessLevel.ADMIN, (AccessLevel.PRIVATE_USER,))
        return select_rss(rss_data, "xml")

    # 登录用户可以无条件访问的源
    if rss_data := data.rss_cache.get_source_or_None(source_name, AccessLevel.SHARED_USER):
        return select_rss(rss_data, "xml")
    # 登录用户对于 USER 级别能访问的
    accessed_src_names = UserRegistry.get_sources_by_name(user.name)
    if source_name in accessed_src_names:
        rss_data = data.rss_cache.get_source_or_None(source_name, AccessLevel.ADMIN)
        return select_rss(rss_data, "xml")

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"the source '{source_name}' is not accessed by '{user.name}'"
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

async def no_cache_flow(cls_id: str, one_group_params: tuple) -> str:
    scraper_with_one_group_params = ScraperNameAndParams.create(cls_id, (one_group_params, ))
    try:
        res = await start_to_crawl((scraper_with_one_group_params, ))
    except CrawlInitError as e:
        raise HTTPException(status_code=e.code, detail=str(e))

    try:
        return res[0][0]
    except IndexError:
        await config.post2RSS("error log of no_cache_flow", f"{res=}, {cls_id=}, {one_group_params=}")
        raise HTTPException(status_code=500, detail="crawl result is not expected")

@async_cached
async def cache_flow(cls_id: str, one_group_params: tuple) -> str:
    return await no_cache_flow(cls_id, one_group_params)

@router.get("/{cls_id}/")
async def query_rss(cls_id: str, user: Annotated[User, Depends(get_valid_user)], q: Annotated[list[str], Query()] = []):
    """已登录用户可以用此主动请求更新，并获取更新后的源"""
    if Plugins.get_plugin_or_none(cls_id) is None or cls_id == "Representative":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scraper Not Found")
    # todo 检查，用户只能请求用户级别的抓取器
    if user.is_administrator and not config.in_bedtime(cls_id, datetime.now().strftime("%H:%M")):
        logger.info(f"{cls_id} get new request of {q}, go to no_cache_flow")
        source_name = await no_cache_flow(cls_id, tuple(q))
        rss_data = data.rss_cache.get_source_or_None(source_name, AccessLevel.ADMIN)
    else: # 对于普通用户，通过缓存防止滥用
        logger.info(f"{cls_id} get new request of {q}, go to cache_flow")
        source_name = await cache_flow(cls_id, tuple(q))
        # 能触发就能访问，因此这里直接找 source_name 对应的即可
        rss_data = data.rss_cache.get_source_or_None(source_name, AccessLevel.PRIVATE_USER)
    return select_rss(rss_data, "xml")
