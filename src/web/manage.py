"""供管理员使用的管理类接口"""
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from src.crawl import start_to_crawl_all

from .get_rss import templates
from .security import User, UserRegistry, get_admin_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/manage",
    tags=[__name__],
)

@router.get("/", response_class=HTMLResponse, dependencies=[Depends(get_admin_user)])
async def manage_page(request: Request):
    return templates.TemplateResponse(request=request, name="manage.html")


# todo 可能会出现同一个抓取器同时运行，会有什么影响
@router.post("/crawler/run_all", response_class=JSONResponse, dependencies=[Depends(get_admin_user)])
async def run_all_scraper(background_tasks: BackgroundTasks):
    background_tasks.add_task(start_to_crawl_all)
    return HTMLResponse("<p>start to crawl</p>")


class InviteCodeCreate(BaseModel):
    code: str
    count: int

@router.post("/invite_code", response_class=JSONResponse)
async def update_invite_code(ic_data: InviteCodeCreate, user: Annotated[User, Depends(get_admin_user)]):
    if UserRegistry.update_ic(ic_data.code, ic_data.count, user):
        return {"message": "Invite Code updated"}
    return {"message": "Invite Code failed to be updated"}
