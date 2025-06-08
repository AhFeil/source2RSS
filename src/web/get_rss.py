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
    context = {"rss_list": data.get_rss_list()}
    return templates.TemplateResponse(request=request, name="rss_list.html", context=context)

@router.get("/{f_source_name}.xml/", response_class=PlainTextResponse)
def get_saved_rss(f_source_name: str):
    rss = data.get_rss_or_None(f_source_name)
    if rss is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS content is missed in cache")
    return rss

@router.get("/{f_source_name}.json/", response_class=JSONResponse)
def get_saved_json(f_source_name: str):
    rss_json = data.get_rss_json_or_None(f_source_name)
    if rss_json is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS json is missed in cache")
    return rss_json
