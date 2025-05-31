import time
import asyncio
import threading

import schedule

import preprocess
from src.crawler import start_to_crawl


config = preprocess.config


# https://schedule.readthedocs.io/en/stable/background-execution.html
def run_continuously():
    """Continuously run, while executing pending jobs at each
    elapsed time interval.
    @return cease_continuous_run: threading. Event which can
    be set to cease continuous run 
    cease 停止
    """
    cease_continuous_run = threading.Event()
    # 通过这个 event，控制这个是否循环检查 schedule
    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(config.WAIT)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run


def sync_wrapper(cls_names):
    try:
        asyncio.run(start_to_crawl(cls_names))
    except:
        import traceback
        with open("unpredictable_exception.txt", 'a', encoding="utf-8") as f:
            f.write(traceback.format_exc())

job = sync_wrapper

for point, cls_names in config.get_schedule_and_cls_names(preprocess.Plugins.get_all_id()).items():
    schedule.every().day.at(point, config.timezone).do(job, cls_names)
    print(point, cls_names)
for job_info in schedule.get_jobs():
    print(job_info.next_run)


if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(config.WAIT)
    # .env/bin/python -m src.run_as_scheduled
