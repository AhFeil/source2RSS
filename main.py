import asyncio
import logging
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

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
    context = {"ad_html": config.ad_html, "crawl_schedules": config.get_crawl_schedules()}
    return get_rss.templates.TemplateResponse(request=request, name="home.html", context=context)


app = socketio.ASGIApp(sio, other_asgi_app=fast_app) if config.enable_agent_server else fast_app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.port)
