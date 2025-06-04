"""供管理员使用的管理类接口"""
import logging
import asyncio

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from .security import UserRegistry, Identity

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/manage",
    tags=["manage"],
)

running_lock = asyncio.Lock()

async def start_crawl():
    global running_lock
    if running_lock.locked():
        logger.info("is crawling now")
        return
    async with running_lock:
        from src.crawler import start_to_crawl
        from preproc import Plugins
        await start_to_crawl(Plugins.get_all_id())

# todo 可能会出现同一个抓取器同时运行，会有什么影响
@router.post("/crawler/run_all", response_class=JSONResponse)
async def run_all_scraper(id: Identity):
    user = UserRegistry.get_valid_user_or_none(id.name, id.passwd)
    if user is None or not user.is_administrator:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    logger.info("start to crawl")
    asyncio.create_task(start_crawl())
    return {"message": "start to crawl"}
