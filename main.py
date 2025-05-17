import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from preprocess import data
from dataHandle import SourceMeta, ArticleInfo, PublishMethod
from src.run_as_scheduled import run_continuously
from src.generate_rss import generate_rss_from_collection


logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background thread
    stop_run_continuously = run_continuously()

    # Do some other things...
    yield

    # Stop the background thread
    stop_run_continuously.set()


app = FastAPI(lifespan=lifespan)


@app.get("/source2rss/{source_file_name}/", response_class=PlainTextResponse)
async def get_info(source_file_name: str):
    rss = data.get_rss_or_None(source_file_name)
    if rss is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return rss


# 现在无法覆盖原有数据
@app.put("/rss_info/{user_name}/{source_name}")
@app.post("/rss_info/{user_name}/{source_name}")
async def add_rss(user_name: str, source_name: str, source_meta: SourceMeta):
    meta = source_meta.model_dump()
    data.exist_source_meta(meta)
    return {"state": "true"}


@app.get("/rss_info/{user_name}/{source_name}/")
async def get_info(user_name: str, source_name: str):
    source_info = data.get_source_info(source_name)
    key4sort = source_info["key4sort"]
    collection = data.db[source_name]
    result = collection.find({}, {key4sort: 1}).sort(key4sort, -1).limit(1)
    result = list(result)
    last_update_flag = result[0][key4sort] if result else False
    if key4sort in {"pub_time"}:
        last_update_flag = last_update_flag.timestamp()
    return {"last_update_flag": last_update_flag}


@app.post("/rss_items/{user_name}/{source_name}/")
async def delivery(user_name: str, source_name: str, articles: list[ArticleInfo], pub_method: PublishMethod):
    key4sort = pub_method.key4sort
    for a in articles:
        a = a.model_dump()
        one_article_etc = {
            "article_infomation": a, 
            key4sort: a[key4sort]
        }
        data.store2database(source_name, one_article_etc)
        logger.info(f"{source_name} have new article: {a['article_name']}")
    
    source_info = data.get_source_info(source_name)
    if source_info:
        # 生成 RSS 并保存到目录
        generate_rss_from_collection(source_info, data.db[source_name])
        return {"state": "true", "link": "https://rss.vfly2.com/source2rss/"}
    else:
        return {"state": "false", "notice": "please /add_rss firstly"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=7500)

    # uvicorn main:app --host 0.0.0.0 --port 7500
