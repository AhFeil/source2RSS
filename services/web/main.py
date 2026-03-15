import asyncio
import logging
from contextlib import asynccontextmanager
from enum import StrEnum
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from src.config_handle import config
from src.data_handle import Plugins
from src.run_as_scheduled import run_continuously
from src.web import get_rss, manage, post_src, query_rss, usage, user

logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the background thread
    loop = asyncio.get_running_loop()
    stop_run_continuously = run_continuously(loop)

    # Do some other things...
    yield
    # Stop the background thread
    stop_run_continuously.set()


app = FastAPI(lifespan=lifespan)

app.include_router(get_rss.router)
app.include_router(post_src.router)
app.include_router(query_rss.router)
app.include_router(usage.router)
app.include_router(user.router)
app.include_router(manage.router)

for module in Plugins.imported_modules.values():
    if "router" in getattr(module, "__all__", []):
        app.include_router(module.router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    context = {"crawl_schedules": config.get_crawl_schedules()}
    return get_rss.templates.TemplateResponse(request=request, name="home.html", context=context)


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(path="src/web/static/favicon.ico", filename="favicon.ico")


class AdditionalPage(StrEnum):
    robots = "robots.txt"
    sitemap = "sitemap.xml"

additional_pages = {
    item.value: Path(f"src/web/templates/{item.value}").read_text(encoding="utf-8")
    for item in AdditionalPage
}

@app.get("/{file}", response_class=PlainTextResponse)
async def static_from_root(file: AdditionalPage):
    return additional_pages[file.value]


if config.http_proxy_url:
    import os

    os.environ["http_proxy"] = config.http_proxy_url
    os.environ["https_proxy"] = config.http_proxy_url

    print("set proxy:", config.http_proxy_url)  # noqa: T201
