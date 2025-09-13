# source2RSS

source2RSS 是一个通用的**信息源转 RSS** 的 Python 框架，提供生成 RSS、用户访问 RSS 权限管理、web 界面、分布式抓取、主动发布 RSS 等功能。

如果想获得某个网站的 RSS，只需要为其编写一个抓取器，目前项目有 10 多个抓取器示例，覆盖了较多的场景，可供编写时参考。较为实用的有 **B 站 up 动态的 RSS** 和 **YouTube Channel 的 RSS**（比官方多了视频时长，方便筛除短视频）。

另一个比较实用的是**主动发布 RSS**，提供了 Python 版的客户端（已发布到 PyPI `pip install source2RSS_client`）。使用上就是向一个 API 发送信息的标题和内容，然后就可以在 RSS 阅读器上等着接收。作者目前将之用在通知程序运行中遇到的非预期的异常。

> 创建这个项目，是为了方便制作 RSS 源。抓取结构简单的网站的数据并不困难，半小时到一小时，但是要想实现订阅，还需要制成 RSS、保留历史文章、定期运行、提供网址和访问等功能。
>
> 这个框架的核心，就是让用户只需要关注信息源的抓取和格式化，其余的交给框架。
>
> 由于不熟悉 JS、TS 语言，所以没有选择 RSSHub ，而是写一个 Python 版的框架。随着实际使用，挖掘出了很多需求，source2RSS 的功能也越来越强大，但同时保持着清晰的架构。

~~对于 Python 新人，尤其是对爬虫感兴趣的，相信这个项目很适合参考。~~ 以及欢迎熟悉 Python 的朋友提建议。


## 使用

**最终就是提供一个订阅链接**。

### 网站的 RSS

由作者维护的服务提供的 RSS 源有这些： https://rss.vfly2.com/source2rss/ ，并不多，只是作者本人根据需要写的抓取器，如果其中有对你有用的，可以直接订阅。

如果你了解 Python，也可以参考项目中 [scraper examples](src/scraper/examples) 这里的抓取器，编写一个抓取器。如果你想贡献给社区，可以提交到本仓库，作者的服务将运行该抓取器，从而在 https://rss.vfly2.com/source2rss/ 这里提供订阅链接。也可以不公开你的抓取器，自行部署 source2RSS ，然后在配置文件中指定一下该抓取器的模块路径并启用即可，具体后面会讲到。

或者，可以找作者**定制网站 RSS**，详情查看 https://tashcp.com/2025/06/customize-rss/ 。


### 主动发布 RSS

使用 Python 客户端：[client/README.md](client/README.md)

使用 curl 发布：

```sh
curl -X 'POST' \
  'http://127.0.0.1:8536/post_src/source2rss_severe_log/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Basic $(echo -n 'vfly2:123456' | base64 | tr -d '\n')" \
  -d '[
  {
    "title": "test post from curl 1",
    "link": "https://yanh.tech/1",
    "summary": "xx",
    "pub_time": 2
  },
  {
    "title": "test post from curl 2",
    "link": "https://yanh.tech/2",
    "summary": "yy",
    "pub_time": 3
  }
]'
```

其他语言暂时没有提供相应的客户端，可以参考 Python 和 curl 的自行实现。

发布新文章使用 `/post_src/{source_name}` 这个端口，每个文章可以包含的所有字段由 ArticleInfo 决定，因此不必受上面例子的影响，它们使用的都是最少的字段，其他字段会由 source2RSS 填充为默认值，以此减小使用时不必要的思考。


## 管理员

对于访客，本项目提供的功能只有访问公开订阅源；但是对于管理员，则有很多功能可以使用。

首先需要部署自己的实例： [信息源转 RSS 框架 - source2RSS 的安装步骤 - 技焉洲 (yanh.tech)](https://yanh.tech/2024/07/deployment-process-for-source2rss/)

然后……（TODO 待写）

对于如何订阅 B 站 up 动态，以及其他抓取器的用法，可以到首页的“用法”里查看。


### 触发抓取的方式

触发抓取有两种方式：
1. 定期运行。配置文件可以设置每种抓取器定期运行的时间
2. 主动请求触发。比如访问 http://rss.vfly2.com/query_rss/BilibiliUp/?q=483246073 ，就会触发抓取某个 B 站 up 的动态，并把最新的结果返回。

定期运行由配置文件决定，因此只有管理员能使用。

为了避免滥用，主动请求不响应访客的请求，只对普通用户和管理员响应；不同的是，普通用户在触发一次后，会有一段时间的不应期，这段时间里该用户的请求不会触发抓取，之后返回当时的结果；而管理员每次请求都会触发抓取。


### 访问源的多种方式

无须凭证

/source2RSS/{table_name.xml}

/source2RSS/{user_name}/{table_name.xml}

需要凭证

/query_rss/{table_name.xml}

如 http://vfly2:123456@127.0.0.1:8536/query_rss/source2rss_severe_log.xml/


/query_rss/{class_id}?q=xx


### 为用户添加访问某 RSS 的权限


## 开发

编写抓取器，可以查看文档：[scraper.md](docs/scraper.md)

为框架贡献代码，可以参考文档：[design.md](docs/design.md)
