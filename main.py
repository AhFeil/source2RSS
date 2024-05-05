import logging
import signal
import asyncio

from crawler import monitor_website
from generate_rss import generate_rss

logger = logging.getLogger("main")


async def main():
    import preprocess

    config = preprocess.config
    data = preprocess.data
    plugins = preprocess.plugins

    # 开发环境下，每次都把集合清空
    if not config.is_production:
        data._clear_db()
    
    def handler(sig, frame):
        # 退出前清理环境
        exit(0)
    signal.signal(signal.SIGINT, handler)

    await monitor_website(config, data, plugins)


if __name__ == "__main__":
    asyncio.run(main())
    
    
