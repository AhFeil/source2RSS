import logging
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI

from src.web import get_rss, post_src, query_rss, user, manage
from src.run_as_scheduled import run_continuously
from preproc import Plugins


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
app.include_router(user.router)
app.include_router(manage.router)

for path, module in Plugins.imported_modules.items():
    if "router" in getattr(module, "__all__", []):
        app.include_router(module.router)


@app.get("/")
async def index():
    return {"message": "Source2RSS HomePage"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=7500)
