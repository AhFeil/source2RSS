"""各个抓取器的用法和一些发起请求的快捷方式"""
import inspect
import logging
from contextlib import suppress

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from preproc import Plugins, config

from .get_rss import templates

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/usage",
    tags=[__name__],
)


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
        args_l = config.get_params(class_name)
        if args_l[0] is None:
            desc.append("<p>缺失例子</p>")
        else:
            for args in args_l:
                if not isinstance(args, list):
                    args = [args]
                safe_args = [("xxxxx-secret-xxxxx" if secret_index[i] else str(arg)) for i, arg in enumerate(args)]
                link = f"/query_rss/{class_name}/?q=" + "&q=".join(safe_args)
                instance = await scraper_class.create(*args)
                desc.append(f'<p><span>{instance.source_info["name"]} 的 RSS 链接：</span> <a href="{link}">{link}</a></p>')
                instance.destroy() # todo
    else:
        link = f"/query_rss/{class_name}/"
        instance = await scraper_class.create()
        desc.append(f'<p><span>{instance.source_info["name"]} 的 RSS 链接：</span> <a href="{link}">{link}</a></p>')
        instance.destroy() # todo
    return "\n".join(desc)


@router.get("/", response_class=HTMLResponse)
async def usage_page(request: Request):
    context = {"all_scrapers": tuple(Plugins.get_all_id())}
    return templates.TemplateResponse(request=request, name="usage.html", context=context)

# todo 使用缓存
@router.get("/{cls_id}/", response_class=HTMLResponse)
async def usage_of_scraper(request: Request, cls_id: str):
    scraper_class = Plugins.get_plugin_or_none(cls_id)
    if not scraper_class:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scraper Not Found")
    desc = await make_desc(scraper_class)
    context = {"cls_id": cls_id, "desc": desc}
    return templates.TemplateResponse(request=request, name="scraper_usage.html", context=context)
