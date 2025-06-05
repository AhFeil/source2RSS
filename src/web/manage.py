"""供管理员使用的管理类接口"""
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse

from src.crawler import start_to_crawl_all
from .security import UserRegistry, Identity

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/manage",
    tags=["manage"],
)


# todo 可能会出现同一个抓取器同时运行，会有什么影响
@router.post("/crawler/run_all", response_class=JSONResponse)
async def run_all_scraper(id: Identity, background_tasks: BackgroundTasks):
    user = UserRegistry.get_valid_user_or_none(id.name, id.passwd)
    if user is None or not user.is_administrator:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    logger.info("start to crawl")
    background_tasks.add_task(start_to_crawl_all)
    return {"message": "start to crawl"}
