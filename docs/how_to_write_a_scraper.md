
> 本文主要是为 AI 写的。

文章中出现的路径都是相对于项目根目录的相对路径。如果找不到文件，则发出提醒并**停止运行**。

需求方需要给出“网址”和“要抓取的内容”（比如给出第一个文章的标题，我们借此可以推理出要抓取的内容是哪些）。

步骤：
1. 首先查看一下 `src/scraper/scraper.py` 文件，里面有抓取器基类 `WebsiteScraper` 的代码，了解需要实现哪些接口。
2. 查看几个现存的抓取器示例，他们分别是 `src/scraper/examples/bentoml.py`、`src/scraper/examples/cslrxyz.py`、`src/scraper/examples/telegram_channel.py`、`src/scraper/examples/youtube_channel.py`、`src/scraper/examples/bilibili_up.py`，从而理解怎么实现。
3. 查看 `src/scraper/tools.py` 里面提供的抓取工具，主要是使用 httpx 的 `get_response_or_none` 和使用 playwright 的 `AsyncBrowserManager`，在编写抓取器时，优先使用这里面提供的工具类或工具函数，如果不能满足需要，再自己实现代码。优先使用基于 http 请求的工具，而不是基于无头浏览器的工具。
4. 在 `src/scraper/examples` 下面创建一个新文件，并编写抓取器代码。
    1. 第一次先仅实现获取 HTML 或其他类型的数据（如果因为反爬或者网络不可用导致没能获取，就发出提醒并**停止运行**，由外部解决这类问题），然后修改 `src/scraper/try_scraper.py` 里面的抓取类（无须在完成任务后还原），调用执行一次，获得并查看数据、了解结构，找到需要抓取的内容；
    2. 如果发现了这个信息源本身提供的 RSS 链接，则发出提醒并**停止运行**；
    3. 第二次补充上从数据中提取所需内容的代码，并再次执行，查看效果；
    4. 如果抓取成功，则**停止运行**，否则根据结果修改代码，重新执行，最多迭代 10 次。
5. 在程序中测试。后台启动 source2RSS，从 `examples/config.example.yaml` 获取管理员名称和密码用以基本校验，然后通过 API 触发这个抓取器的运行，即访问 `http://localhost:8536/query_rss/{Scraper Class Name}/?q={}`，如果没有抓取器参数就不携带 q 查询参数。检查是否能触发并返回正确的 RSS。

下面内容仅为记录，不一定要遵守：
- 如果网站提供了站点地图，可以考虑使用站点地图里面的数据。
