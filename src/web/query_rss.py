# ruff: noqa: B904
"""主动请求某个源的 RSS ，会触发抓取过程并返回结果"""
import logging
from datetime import datetime
from enum import Enum, auto
from functools import wraps
from itertools import chain
from typing import Annotated

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse

from preproc import Plugins, config, data
from src.crawl import ScraperNameAndParams, start_to_crawl
from src.crawl.crawl_error import CrawlError
from src.scraper import AccessLevel

from . import sort_rss_list
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
    if user.is_administrator:
        user_rss = data.rss_cache.get_source_list(AccessLevel.ADMIN, AccessLevel.PUBLIC, (AccessLevel.PRIVATE_USER, ))
    else:
        user_rss = data.rss_cache.get_source_list(AccessLevel.SHARED_USER, AccessLevel.PUBLIC)
    auth_rss_groups = sort_rss_list([
        (table_name, data.rss_cache.get_source_readable_name(table_name))
        for table_name in UserRegistry.get_sources_by_name(user.name)
    ])
    context = {
        "user_rss_groups": sort_rss_list(user_rss),
        "auth_rss_groups": auth_rss_groups,
        "user_name": user.name,
    }
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

class CacheType(Enum):
    NORMAL = auto()
    JUST_REFRESH = auto()    # 不管缓存里的，总是执行，并把结果放到缓存中
    JUST_SKIP_CACHE = auto() # 总是执行，不把结果放缓存中

cache=TTLCache(maxsize=config.query_cache_maxsize, ttl=config.query_cache_ttl_s)

def async_cached(func):
    @wraps(func)
    async def wrapper(cls_id: str, one_group_params: tuple, cache_type: CacheType):
        if cache_type is CacheType.JUST_SKIP_CACHE:
            return await func(cls_id, one_group_params, cache_type=cache_type)
        # 根据传入的参数生成唯一的 key
        cache_key = (cls_id, one_group_params)
        if cache_type is CacheType.NORMAL and cache_key in cache:
            logger.debug("%s, %s, has cache", cls_id, str(one_group_params))
            return cache[cache_key]
        logger.debug("%s, %s, will crawl immediately", cls_id, str(one_group_params))
        try:
            result = await func(cls_id, one_group_params, cache_type=cache_type)
            cache[cache_key] = result
        except HTTPException as e:
            if e.status_code != 466:
                raise
            # 对于不应期，尝试返回缓存中的值
            result = cache.get(cache_key)
            if not result:
                raise
        return result
    return wrapper

@async_cached
async def go_to_crawl(cls_id: str, one_group_params: tuple, *, cache_type: CacheType=CacheType.NORMAL) -> str:
    scraper_with_one_group_params = ScraperNameAndParams.create(cls_id, (one_group_params, ))
    try:
        res = await start_to_crawl((scraper_with_one_group_params, ))
    except CrawlError as e:
        raise HTTPException(status_code=e.code, detail=str(e))

    try:
        return res[0][0]
    except IndexError:
        await config.post2RSS("error log of no_cache_flow", f"{res=}, {cls_id=}, {one_group_params=}")
        raise HTTPException(status_code=500, detail="crawl result is not expected")

@router.get("/{cls_id}/")
async def query_rss(cls_id: str, user: Annotated[User, Depends(get_valid_user)], q: Annotated[list[str], Query()] = []): # noqa: B006
    """已登录用户可以用此主动请求更新，并获取更新后的源"""
    if Plugins.get_plugin_or_none(cls_id) is None or cls_id == "Representative":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scraper Not Found")
    logger.info(f"{cls_id} get new request of {q}")
    # todo 检查，用户只能请求用户级别的抓取器
    if user.is_administrator and not config.in_bedtime(cls_id, datetime.now().strftime("%H:%M")):
        source_name = await go_to_crawl(cls_id, tuple(q), cache_type=CacheType.JUST_REFRESH)
        rss_data = data.rss_cache.get_source_or_None(source_name, AccessLevel.ADMIN)
    else: # 对于普通用户，通过缓存防止滥用
        source_name = await go_to_crawl(cls_id, tuple(q), cache_type=CacheType.NORMAL)
        # 能触发就能访问，因此这里直接找 source_name 对应的即可
        rss_data = data.rss_cache.get_source_or_None(source_name, AccessLevel.PRIVATE_USER)
    return select_rss(rss_data, "xml")
