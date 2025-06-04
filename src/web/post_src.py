""""""
import logging

from fastapi import APIRouter

from src.website_scraper import SourceMeta, ArticleInfo, PublishMethod
from src.generate_rss import generate_rss
from preproc import data

logger = logging.getLogger("post_rss")

router = APIRouter(
    prefix="/post_rss",
    tags=["post_rss"],
)

# 现在无法覆盖原有数据
@router.put("/rss_info/{user_name}/{source_name}")
@router.post("/rss_info/{user_name}/{source_name}")
async def add_rss(user_name: str, source_name: str, source_meta: SourceMeta):
    meta = source_meta.model_dump(mode="json")
    data.db_intf.exist_source_meta(meta) # type: ignore
    return {"state": "true"}


@router.get("/rss_info/{user_name}/{source_name}/")
async def get_info(user_name: str, source_name: str):
    source_info = data.db_intf.get_source_info(source_name)
    if source_info is None:
        return {"last_update_flag": False}

    key4sort = source_info["key4sort"]
    result = data.db_intf.get_top_n_articles_by_key(source_name, 1, key4sort)
    last_update_flag = result[0][key4sort] if result else False
    if key4sort in {"pub_time"}:
        last_update_flag = last_update_flag.timestamp() # type: ignore
    return {"last_update_flag": last_update_flag}


@router.post("/rss_items/{user_name}/{source_name}/")
async def delivery(user_name: str, source_name: str, articles: list[ArticleInfo], pub_method: PublishMethod):
    key4sort = pub_method.key4sort
    for a in articles:
        a = a.model_dump_to_json()
        data.db_intf.store2database(source_name, a) # type: ignore
        logger.info(f"{source_name} have new article: {a['title']}")

    source_info = data.db_intf.get_source_info(source_name)
    if source_info:
        # 生成 RSS 并保存到目录
        result = data.db_intf.get_top_n_articles_by_key(source_name, 50, key4sort)
        generate_rss(source_info, result)
        return {"state": "true", "link": "https://rss.vfly2.com/source2rss/"}
    else:
        return {"state": "false", "notice": "please /add_rss firstly"}
