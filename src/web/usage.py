# ruff: noqa: B904
"""各个抓取器的用法和一些发起请求的快捷方式"""
import inspect
import logging
from contextlib import suppress

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from data_handle import data
from data_handle import Plugins
from src.crawl.crawler import ScraperNameAndParams
from src.scraper import WebsiteScraper

from .get_rss import templates

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/usage",
    tags=[__name__],
)


def combine_link(desc: list, scraper: ScraperNameAndParams, link: str):
    cls: type[WebsiteScraper] | None = Plugins.get_plugin_or_none(scraper.name)
    if cls is None:
        desc.append('<p>抓取器不存在</p>')
        return
    if scraper.name == "Representative":
        name = "Representative"
    elif scraper.name == "Remote":
        name = "Remote"
    else:
        params = (scraper.init_params,) if isinstance(scraper.init_params, str) else scraper.init_params
        table_name = cls.table_name_formation.format(*params)
        source_info = data.db_intf.get_source_info(table_name)
        name = source_info["name"] if source_info else "Unknown Name"
    desc.append(f'<p><span>{name} 的 RSS 链接：</span> <a href="{link}" rel="noprerender">{link}</a></p>')


async def make_desc(cls_id: str) -> str:
    desc = []
    secret_index = []
    scraper_class = Plugins.get_plugin_or_none(cls_id)
    if not scraper_class:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scraper Not Found")

    if doc := inspect.getdoc(scraper_class.create):
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
        scrapers = ScraperNameAndParams.create(cls_id, i_am_remote=True)
        if not scrapers:
            desc.append("<p>缺失例子</p>")
        else:
            for scraper in scrapers[:3]:
                if scraper.name == "Remote":
                    args = scraper.init_params[2:]
                else:
                    args = [scraper.init_params] if not isinstance(scraper.init_params, list | tuple) else scraper.init_params
                safe_args = [("xxxxx-secret-xxxxx" if secret_index[i] else str(arg)) for i, arg in enumerate(args)]
                link = f"/query_rss/{cls_id}/?q=" + "&q=".join(safe_args)
                combine_link(desc, scraper, link)
    else:
        link = f"/query_rss/{cls_id}/"
        scraper = ScraperNameAndParams.create(cls_id, i_am_remote=True)[0]
        combine_link(desc, scraper, link)
    return "\n".join(desc)


@router.get("/", response_class=HTMLResponse)
async def usage_page(request: Request):
    context = {"all_scrapers": sorted(Plugins.get_all_id_with_name(), key=lambda x: x[0])}
    return templates.TemplateResponse(request=request, name="usage.html", context=context)


_usage_cache = {}

async def get_usage_of_scraper(cls_id: str) -> str:
    if desc := _usage_cache.get(cls_id):
        return desc
    desc = await make_desc(cls_id)
    _usage_cache[cls_id] = desc
    return desc

@router.get("/{cls_id}/", response_class=HTMLResponse)
async def usage_of_scraper(request: Request, cls_id: str):
    desc = await get_usage_of_scraper(cls_id)
    context = {"cls_id": cls_id, "desc": desc}
    return templates.TemplateResponse(request=request, name="scraper_usage.html", context=context)
