""""""
import logging
from typing import Annotated
from functools import wraps

from cachetools import TTLCache
from fastapi import APIRouter, Query, HTTPException, status, Depends
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasicCredentials

from src.website_scraper import WebsiteScraper, CreateByInvalidParam, FailtoGet
from src.local_publish import goto_uniform_flow
from preprocess import Plugins, data, config
from .security import security
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

@async_cached
async def process_crawl_flow(cls_id: str, cls: WebsiteScraper, q: tuple) -> str:
    try:
        instance = await cls.create(*q)
    except TypeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The amount of parameters is incorrect")
    except CreateByInvalidParam:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid parameters")
    except FailtoGet:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed when crawling")
    except Exception as e:
        logger.error(f"fail when query rss {cls_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unknown Error")
    else:
        return await goto_uniform_flow(data, instance, config.get_amount(cls_id))

@router.get("/{cls_id}/", response_class=PlainTextResponse)
async def query_rss(cls_id: str, q: Annotated[list[str], Query()] = [],
                    credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != config.query_username or credentials.password != config.query_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    logger.info(f"{cls_id} get new request of {q}")
    cls: WebsiteScraper | None = Plugins.get_plugin_or_none(cls_id) # type: ignore
    if cls is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scraper Not Found")
    if not cls.is_variety:
        rss = get_saved_rss(cls.__name__)
        return rss
    source_file_name = await process_crawl_flow(cls_id, cls, tuple(q))
    return get_saved_rss(source_file_name)
