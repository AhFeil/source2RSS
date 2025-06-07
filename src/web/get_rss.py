""""""
import logging

from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasicCredentials

from src.website_scraper import AccessLevel
from preproc import data
from .security import security, UserRegistry

logger = logging.getLogger("get_rss")

router = APIRouter(
    prefix="/source2rss",
    tags=["source2rss"],
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


@router.get("/{username}/{f_source_name}.xml/", response_class=PlainTextResponse)
def get_saved_rss_of_user(username: str, f_source_name: str, credentials: HTTPBasicCredentials = Depends(security)):
    meta = data.db_intf.get_source_info(f_source_name)   # todo f_source_name 和 source_name 不一样
    if meta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS doesn't exist")

    if meta.get("access") == AccessLevel.ADMIN:
        if credentials is not None:
            user = UserRegistry.get_valid_user_or_none(credentials.username, credentials.password)
            if user is not None and user.is_administrator:
                rss = data.get_rss_or_None(f_source_name)
                if rss is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS content is missed in cache")
                return rss
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="only admin can access",
        headers={"WWW-Authenticate": "Basic"},
    )
