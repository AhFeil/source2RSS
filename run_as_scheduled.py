import time
import asyncio
import threading

import schedule

import preprocess
from crawler import main


config = preprocess.config


# https://schedule.readthedocs.io/en/stable/background-execution.html
def run_continuously(interval=1):
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
                time.sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run


def sync_wrapper():
    asyncio.run(main())

job = sync_wrapper


if config.is_production:
    for point in config.run_everyday_at:
        schedule.every().day.at(point, config.timezone).do(job)
    for job_info in schedule.get_jobs():
        print(job_info.next_run)
else:
    schedule.every(config.run_test_every_seconds).seconds.do(job)



if __name__ == "__main__":
    while True:
        schedule.run_pending()
        time.sleep(config.WAIT)

