import asyncio
import logging
from contextlib import asynccontextmanager
from enum import StrEnum
from pathlib import Path

import socketio
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

from preproc import Plugins, config
from src.node import sio
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


fast_app = FastAPI(lifespan=lifespan)

fast_app.include_router(get_rss.router)
fast_app.include_router(post_src.router)
fast_app.include_router(query_rss.router)
fast_app.include_router(usage.router)
fast_app.include_router(user.router)
fast_app.include_router(manage.router)

for module in Plugins.imported_modules.values():
    if "router" in getattr(module, "__all__", []):
        fast_app.include_router(module.router)


@fast_app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    context = {"crawl_schedules": config.get_crawl_schedules()}
    return get_rss.templates.TemplateResponse(request=request, name="home.html", context=context)


@fast_app.get("/favicon.ico")
async def favicon():
    return FileResponse(path="src/web/static/favicon.ico", filename="favicon.ico")


class AdditionalPage(StrEnum):
    robots = "robots.txt"
    sitemap = "sitemap.xml"

additional_pages = {
    item.value: Path(f"src/web/templates/{item.value}").read_text(encoding="utf-8")
    for item in AdditionalPage
}

@fast_app.get("/{file}", response_class=PlainTextResponse)
async def static_from_root(file: AdditionalPage):
    return additional_pages[file.value]

app = socketio.ASGIApp(sio, other_asgi_app=fast_app) if config.enable_agent_server else fast_app


if config.enable_radar:
    from fastapi_radar import Radar

    from preproc import data

    radar = Radar(fast_app, db_engine=data.db_intf.engine, db_path=config.data_dir)
    radar.create_tables()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.port)
