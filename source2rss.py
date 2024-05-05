import logging
from contextlib import asynccontextmanager

from preprocess import config, data
from run_as_scheduled import run_continuously
from dataHandle import SourceMeta, PublishContent
from generate_rss import generate_rss_from_collection

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
    data.exist_source_meta(meta)
    return {"state": "true"}



@app.post("/generate_rss")
async def delivery(pub_content: PublishContent):
    source_name = pub_content.source_name
    key4sort = pub_content.key4sort
    a = dict(pub_content.article_infomation)

    one_article_etc = {
        "article_infomation": a, 
        key4sort: a[key4sort]
    }
    print(one_article_etc)
    data.store2database(source_name, one_article_etc)
    logger.info(f"{source_name} have new article: {pub_content.article_infomation.article_name}")
    
    source_info = data.get_source_info(source_name)
    if source_info:
        # 生成 RSS 并保存到目录
        generate_rss_from_collection(source_info, data.db[source_name], key4sort, config.rss_dir)
        return {"state": "true", "link": "https://rss.vfly2.com/"}
    else:
        return {"state": "false", "notice": "please /add_rss firstly"}

