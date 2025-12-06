import asyncio
import logging
import threading
import time
import traceback
from asyncio import run_coroutine_threadsafe

import schedule

from preproc import Plugins, config
from src.crawl import ScraperNameAndParams, start_to_crawl
from src.crawl.crawl_error import CrawlError

logger = logging.getLogger(__name__)


def sync_wrapper(cls_names, loop):
    try:
        future = run_coroutine_threadsafe(start_to_crawl(ScraperNameAndParams.create(name) for name in cls_names), loop)
        future.result()
    except CrawlError as e:
        if e.code in (400, 422, 500):
            raise # 已知的错误就抑制
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Exception occurred: {e.__class__.__name__}\n{tb}")
        run_coroutine_threadsafe(config.post2RSS("error log of run_as_scheduled", tb), loop)

job = sync_wrapper


# https://schedule.readthedocs.io/en/stable/background-execution.html
def run_continuously(loop: asyncio.AbstractEventLoop):
    """Continuously run, while executing pending jobs at each
    elapsed time interval.
    @return cease_continuous_run: threading. Event which can
    be set to cease continuous run
    """
    cease_continuous_run = threading.Event()
    # 通过这个 event，控制这个是否循环检查 schedule
    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            crawl_schedules = config.get_schedule_and_cls_names(Plugins.get_all_id())
            config.set_crawl_schedules(crawl_schedules)
            for point, cls_names in crawl_schedules.items():
                schedule.every().day.at(point, config.timezone).do(job, cls_names, loop)

            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(config.WAIT)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run


if __name__ == "__main__":
    async def go():
        loop = asyncio.get_running_loop()
        stop_run_continuously = run_continuously(loop)
        await asyncio.sleep(36000)
        stop_run_continuously.set()

    asyncio.run(go())
    # .env/bin/python -m src.run_as_scheduled
