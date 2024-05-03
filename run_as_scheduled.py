import schedule
import time
import asyncio

import preprocess
from main import main

config = preprocess.config

def sync_wrapper():
    asyncio.run(main())

job = sync_wrapper
if config.is_production:
    point = config.run_everyday_at
    # schedule.every().day.at(point).do(job)
    schedule.every().hour.do(job)
else:
    schedule.every(config.run_test_every_seconds).seconds.do(job)


while True:
    schedule.run_pending()
    time.sleep(config.WAIT)

