"""能公开访问的 RSS ，无须用户验证"""
import logging

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from preproc import data

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/source2rss",
    tags=[__name__],
)

templates = Jinja2Templates(directory='src/web/templates')

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def get_rss_list(request: Request):
    context = {"rss_list": data.rss_cache.get_rss_list()}
    return templates.TemplateResponse(request=request, name="rss_list.html", context=context)

@router.get("/{source_name_with_suffix}/")
def get_saved_rss(source_name_with_suffix: str):
    source_name, suffix = source_name_with_suffix.rsplit(".", 1)
    rss_data = data.rss_cache.get_rss_or_None(source_name)
    if rss_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS content is missed in cache")
    if suffix == "xml":
        return PlainTextResponse(rss_data.xml)
    elif suffix == "json":
        return JSONResponse(rss_data.json)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="suffix is not supported")
