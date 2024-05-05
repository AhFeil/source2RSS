import logging
import asyncio
from contextlib import asynccontextmanager

from preprocess import config
from run_as_scheduled import run_continuously
from dataHandle import SourceMeta, ArticleInfo
from generate_rss import generate_rss

from fastapi import FastAPI

logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background thread
    stop_run_continuously = run_continuously(config.WAIT)

    # Do some other things...
    yield

    # Stop the background thread
    stop_run_continuously.set()

app = FastAPI(lifespan=lifespan)


@app.post("/add_rss")
async def add_rss(source_meta: SourceMeta):
    meta = source_meta.model_dump()
    return meta


@app.post("/generate_rss")
async def delivery(article_info: ArticleInfo):
    data = article_info.model_dump()
    return data