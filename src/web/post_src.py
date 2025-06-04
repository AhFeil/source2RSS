"""通过 API 向 source2RSS 发送消息，以 RSS 发布"""
import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.website_scraper.examples.representative import Representative
from src.website_scraper import SourceMeta, ArticleInfo
from preproc import data
from .query_rss import no_cache_flow
from .security import UserRegistry

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/post_src",
    tags=["post_src"],
)

# 现在无法覆盖原有数据
@router.put("/rss_info/{user_name}/{source_name}")
@router.post("/rss_info/{user_name}/{source_name}")
async def add_rss(user_name: str, source_name: str, source_meta: SourceMeta):
    meta = source_meta.model_dump(mode="json")
    data.db_intf.exist_source_meta(meta) # type: ignore
    return {"state": "true"}


class Delivery(BaseModel):
    name: str
    passwd: str
    articles: list[ArticleInfo]


@router.post("/{source_name}/", response_class=JSONResponse)
async def delivery(source_name: str, d: Delivery):
    """用收到的文章构造一个特殊的抓取器，然后走正常处理流程"""
    user = UserRegistry.get_valid_user_or_none(d.name, d.passwd)
    if user is None or not user.is_administrator:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    logger.info("reveice articles of %s", source_name)
    articles = [a.model_dump_to_json() for a in d.articles]
    # todo 先查询是否有 source meta
    source_file_name = await no_cache_flow("Representative", Representative, ((source_name, articles)))
    return {"message": "succeed to deliver articles of " + source_name, "xml": "http://rss.vfly2.com/source2rss/" + source_file_name}
