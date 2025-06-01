import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.web import get_rss, post_src, query_rss
from src.run_as_scheduled import run_continuously


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

app.include_router(get_rss.router)
app.include_router(post_src.router)
app.include_router(query_rss.router)


@app.get("/")
async def index():
    return {"message": "Source2RSS HomePage"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=7500)
