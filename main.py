import logging
from typing import Annotated
from contextlib import asynccontextmanager
from functools import wraps

from fastapi import FastAPI, Request, Query, HTTPException, status, Depends
from fastapi.responses import PlainTextResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from cachetools import TTLCache

from preprocess import Plugins, data, config
from src.run_as_scheduled import run_continuously
from src.generate_rss import generate_rss
from src.local_publish import goto_uniform_flow
from src.website_scraper import WebsiteScraper, CreateByInvalidParam, FailtoGet, SourceMeta, ArticleInfo, PublishMethod


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
templates = Jinja2Templates(directory='templates')
security = HTTPBasic()


@app.get("/source2rss", response_class=HTMLResponse)
@app.get("/source2rss/", response_class=HTMLResponse)
async def get_rss_list(request: Request):
    context = {"rss_list": data.get_rss_list()}
    return templates.TemplateResponse(request=request, name="rss_list.html", context=context)

@app.get("/source2rss/{source_file_name}/", response_class=PlainTextResponse)
def get_saved_rss(source_file_name: str):
    rss = data.get_rss_or_None(source_file_name)
    if rss is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RSS content is missed in cache")
    return rss


cache=TTLCache(maxsize=config.query_cache_maxsize, ttl=config.query_cache_ttl_s)

def async_cached(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 根据传入的参数生成唯一的 key
        cache_key = (args, frozenset(kwargs.items()))
        if cache_key in cache:
            return cache[cache_key]
        result = await func(*args, **kwargs)
        cache[cache_key] = result
        return result
    return wrapper

@async_cached
async def process_crawl_flow(cls_id: str, cls: WebsiteScraper, q: tuple) -> str:
    try:
        instance = await cls.create(*q)
    except TypeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The amount of parameters is incorrect")
    except CreateByInvalidParam:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid parameters")
    except FailtoGet:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed when crawling")
    except Exception as e:
        logger.error(f"fail when query rss {cls_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unknown Error")
    else:
        return await goto_uniform_flow(data, instance)

@app.get("/query_rss/{cls_id}/", response_class=PlainTextResponse)
async def query_rss(cls_id: str, q: Annotated[list[str], Query()] = [],
                    credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != config.query_username or credentials.password != config.query_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    cls: WebsiteScraper | None = Plugins.get_plugin_or_none(cls_id)
    if cls is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scraper Not Found")
    if not cls.is_variety:
        rss = get_saved_rss(cls.__name__)
        return rss
    source_file_name = await process_crawl_flow(cls_id, cls, tuple(q))
    return get_saved_rss(source_file_name)


# 现在无法覆盖原有数据
@app.put("/rss_info/{user_name}/{source_name}")
@app.post("/rss_info/{user_name}/{source_name}")
async def add_rss(user_name: str, source_name: str, source_meta: SourceMeta):
    meta = source_meta.model_dump(mode="json")
    data.db_intf.exist_source_meta(meta) # type: ignore
    return {"state": "true"}


@app.get("/rss_info/{user_name}/{source_name}/")
async def get_info(user_name: str, source_name: str):
    source_info = data.db_intf.get_source_info(source_name)
    if source_info is None:
        return {"last_update_flag": False}

    key4sort = source_info["key4sort"]
    result = data.db_intf.get_top_n_articles_by_key(source_name, 1, key4sort)
    last_update_flag = result[0][key4sort] if result else False
    if key4sort in {"pub_time"}:
        last_update_flag = last_update_flag.timestamp() # type: ignore
    return {"last_update_flag": last_update_flag}


@app.post("/rss_items/{user_name}/{source_name}/")
async def delivery(user_name: str, source_name: str, articles: list[ArticleInfo], pub_method: PublishMethod):
    key4sort = pub_method.key4sort
    for a in articles:
        a = a.model_dump_to_json()
        data.db_intf.store2database(source_name, a) # type: ignore
        logger.info(f"{source_name} have new article: {a['title']}")

    source_info = data.db_intf.get_source_info(source_name)
    if source_info:
        # 生成 RSS 并保存到目录
        result = data.db_intf.get_top_n_articles_by_key(source_name, 50, key4sort)
        generate_rss(source_info, result) # type: ignore
        return {"state": "true", "link": "https://rss.vfly2.com/source2rss/"}
    else:
        return {"state": "false", "notice": "please /add_rss firstly"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=7500)

    # uvicorn main:app --host 0.0.0.0 --port 7500
