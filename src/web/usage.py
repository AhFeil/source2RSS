# ruff: noqa: B904
"""各个抓取器的用法和一些发起请求的快捷方式"""
import asyncio
import inspect
import logging
import traceback
from contextlib import suppress

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from preproc import Plugins
from src.crawl.crawler import ScraperNameAndParams, discard_scraper, get_instance

from .get_rss import templates

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/usage",
    tags=[__name__],
)


async def combine_link(desc, scraper, link):
    try:
        instance = await get_instance(scraper)
    except Exception:
        desc.append('<p>创建抓取器出错，请稍后重试</p>')
        logger.error(f"usage create instance error, full traceback:\n{traceback.format_exc()}")
    else:
        if instance:
            desc.append(f'<p><span>{instance.source_info["name"]} 的 RSS 链接：</span> <a href="{link}" rel="noprerender">{link}</a></p>')
            asyncio.create_task(discard_scraper(scraper))
            await instance.destroy() # todo
        else:
            desc.append('<p>抓取器不存在或初始化参数有误</p>')

async def make_desc(scraper_class) -> str:
    desc = []
    secret_index = []
    class_name = scraper_class.__name__

    doc = inspect.getdoc(scraper_class.create)
    if doc:
        doc_line = iter(doc.split("\n"))
        with suppress(StopIteration):
            while not next(doc_line).strip().startswith("Args"):
                continue
            desc.append("<p>参数：</p>")
            while not (line := next(doc_line).strip()).endswith(":"):
                desc.append(f"<p>{line}</p>")
                secret_index.append("(secret)" in line)

    desc.append("<br>")
    desc.append("<p>主动查询的网址例子：</p>")
    if scraper_class.is_variety:
        scrapers = ScraperNameAndParams.create(class_name)
        if not scrapers:
            desc.append("<p>缺失例子</p>")
        else:
            for scraper in scrapers:
                if scraper.name == "Remote":
                    args = scraper.init_params[2:]
                else:
                    args = [scraper.init_params] if not isinstance(scraper.init_params, list | tuple) else scraper.init_params
                safe_args = [("xxxxx-secret-xxxxx" if secret_index[i] else str(arg)) for i, arg in enumerate(args)]
                link = f"/query_rss/{class_name}/?q=" + "&q=".join(safe_args)
                await combine_link(desc, scraper, link)
    else:
        link = f"/query_rss/{class_name}/"
        scraper = ScraperNameAndParams.create(class_name)[0]
        await combine_link(desc, scraper, link)
    return "\n".join(desc)


@router.get("/", response_class=HTMLResponse)
async def usage_page(request: Request):
    context = {"all_scrapers": sorted(Plugins.get_all_id_with_name(), key=lambda x: x[0])}
    return templates.TemplateResponse(request=request, name="usage.html", context=context)


_usage_cache = {}

async def get_usage_of_scraper(cls_id: str) -> str:
    if desc := _usage_cache.get(cls_id):
        return desc
    scraper_class = Plugins.get_plugin_or_none(cls_id)
    if not scraper_class:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scraper Not Found")
    desc = await make_desc(scraper_class)
    _usage_cache[cls_id] = desc
    return desc

@router.get("/{cls_id}/", response_class=HTMLResponse)
async def usage_of_scraper(request: Request, cls_id: str):
    desc = await get_usage_of_scraper(cls_id)
    context = {"cls_id": cls_id, "desc": desc}
    return templates.TemplateResponse(request=request, name="scraper_usage.html", context=context)
