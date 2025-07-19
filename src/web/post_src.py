"""通过 API 向 source2RSS 发送消息，以 RSS 发布"""
import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from preproc import data
from src.scraper import AccessLevel, ArticleInfo, SortKey, SourceMeta

from .query_rss import no_cache_flow
from .security import get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/post_src",
    tags=[__name__],
)


@router.put("/", response_class=JSONResponse, dependencies=[Depends(get_admin_user)])
async def update_source(m: SourceMeta):
    meta = m.model_dump(mode="json")
    data.db_intf.exist_source_meta(meta) # type: ignore
    return {"message": "done"}

@router.post("/", response_class=JSONResponse, dependencies=[Depends(get_admin_user)])
async def add_source(m: SourceMeta):
    if data.db_intf.get_source_info(m.name):
        return {"message": "There is already a source with the same name, you can use put to update it"}
    meta = m.model_dump(mode="json")
    data.db_intf.exist_source_meta(meta) # type: ignore
    return {"message": "done"}


@router.post("/{source_name}/", response_class=JSONResponse, dependencies=[Depends(get_admin_user)])
async def delivery(source_name: str, articles: list[ArticleInfo]):
    """用收到的文章构造一个特殊的抓取器，然后走正常处理流程"""
    logger.info("reveice articles of %s", source_name)
    j_articles = [a.model_dump_to_json() for a in articles]
    source = data.db_intf.get_source_info(source_name)
    if source is None:
        source = {
            "name": source_name,
            "link": "http://rss.vfly2.com/",
            "desc": "This RSS service is provided by source2RSS (https://github.com/AhFeil/source2RSS). if you like it, please give a star.",
            "lang": "zh-CN",
            "key4sort": SortKey.PUB_TIME,
            "access": AccessLevel.ADMIN # todo 应该用 LIMITED_USER
        }
    source_name = await no_cache_flow("Representative", ((source, j_articles), ))
    url_without_suffix = "http://rss.vfly2.com/source2rss/" + quote(source_name)
    xml_url = url_without_suffix + ".xml"
    json_url = url_without_suffix + ".json"
    return {"message": "succeed to deliver articles of " + source_name, "xml": xml_url, "json": json_url}
