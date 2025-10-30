
TODO 待写……


source2RSS 框架的职责主要为：
1. 定期或在 API 请求下运行抓取器，可以指定将抓取器实例化时的参数
2. 从抓取器获取文章并保存
3. 格式化为 RSS、JSON 等数据
4. 提供 Web 页面，方便使用

简化流程：【注册抓取器】-【触发（定期运行或主动触发）】-【抓取器返回新的文章】-【保存文章到数据库】-【根据表中数据生成最新的 RSS 文件】-【通过网页访问】


## 源

为了简化模型，将所有文章的输入来源都视作同一种事物，也就是“源（source）”。

源，可以是网站（HTML、JSON、RSS）、API 接口、其他程序通过 API 发来的数据等等。

一个源由两部分组成：
1. 元信息。如源的名称、源的排列方式（比如发布时间、章节数）
2. 文章。这里姑且统一叫文章，文章最少要有标题和用于排列的标志

发布时间是客观必然存在的一种排列标志，在获取源的文章时，可以按时间排序，然后仅获取更新的，再把更新的存入数据库缓存起来，避免每次都要重复获取。根据源的特点，也可以采取其他标志进行排序。


### 名称约定

这里有几个名称关系密切，需要区分清楚。

1. 抓取器的源文件的名称，如 `src/scraper/examples/cslrxyz.py`，指定插件位置时用
2. 抓取器类的名称，如 `CSLRXYZ`，实例化时用，web主动请求时指定抓取器用
3. 数据库中源的表名 table_name ，如 `cslrxyz`，不指定时则使用 source_readable_name，除了用于表名，还会用于 RSS 订阅链接，用以区分不同的 RSS，表名应该尽量只使用 ASCII 字符
4. 源的名称 source_readable_name ，用于展示，比如 RSS 中的名称，在阅读器中将会是这个 RSS 的名称，以及网页上超链接显示的名称，人类可读，因此可以使用任意字符

源文件中可以有多个抓取器类，因此这两个的名称都有作用，不能合并。

table_name 和 source_readable_name 都由类实例的 _source_info() 方法指定，因此是由编写者确定的，也是各有作用，不能和类名合并。

由于历史原因，目前项目中的 source_name 和 table_name 指同一个名称，只是在数据库相关代码里优先用 table_name，在其他地方优先用 source_name；

每个源的 name 可以重复，但是 table_name 不能重复，每个源的 name 可以用 source_readable_name 代替


## Agent

服务 A 运行在有公网的机器上，因此承担对外提供 RSS 的功能，但是该机器性能有限，不能承担大量需要浏览器的抓取器的运行。

服务 B 运行在内网，性能较好。

一种方便服务 A 下发抓取任务给服务 B 的功能。

流程：
1. 内网服务启动后，根据配置文件向公网服务（只能有一个）发送请求，内容有：名称、支持的抓取器列表
2. 公网服务收到后，将内网服务注册，并向其返回注册成功的消息；公网服务可以注册多个内网服务
3. 内网服务和公网服务保存连接，如果意外中断或内网主动停止，则公网服务注销对应的内网服务
4. 公网可以发送需要抓取的数据给内网服务，内网服务收到后，进行相应操作，并把数据返回给公网

公网服务的配置文件中，可以对抓取器设置：本地执行、优先远程执行、必须远程执行。

优先远程意味着如果注册的内网服务中有支持该抓取器的，就用远程执行，否则通过本地。必须远程执行则在没有的情况下，不执行相应任务。

如果内网服务提供的有公网服务不支持的抓取器，公网服务同样可以使用，所有功能和自己支持的一模一样，只是在内网服务断开时，重新提示不支持。

可以设置某个抓取器的执行 agent 列表，在运行时，会随机选一个执行，可以设定权重。

## 时序图


### Web 请求时序图

查看信息源的接口

```mermaid
sequenceDiagram
    actor User
    box FastAPI
    participant get_rss
    participant templates
    end
    box source2RSS
    participant data
    end

    alt 访问根路径
        User->>get_rss: 请求首页
        get_rss->>data: 获取可以公开访问的所有源的名称
        data->>get_rss: 返回所有名称
        get_rss->>templates: 传入数据，渲染页面
        templates->>get_rss: 返回HTML
        get_rss->>User: 返回首页
    else 访问 /{source_name}.xml/
        User->>get_rss: 请求某个源的 RSS
        get_rss->>data: 以源名称获取数据
        data->>get_rss: 返回 RSS 文本
        get_rss->>User: 返回 RSS
    else 访问 /{source_name}.json/
        User->>get_rss: 请求某个源的 JSON
        get_rss->>data: 以源名称获取数据
        data->>get_rss: 返回 JSON
        get_rss->>User: 返回 RSS 的 JSON
    end
```

请求信息源的接口（需要权限）

```mermaid
sequenceDiagram
    actor User
    box FastAPI
    participant query_rss
    end
    box source2RSS
    participant crawler
    participant data
    end

    alt 访问 /{source_name}.xml/
        User->>query_rss: 请求某个源的 RSS
        query_rss->>query_rss: 验证用户，为管理员才继续
        query_rss->>data: 以源名称获取数据
        data->>query_rss: 返回 RSS 文本
        query_rss->>User: 返回 RSS
    else 访问 /{cls_id}/?q=xx&q=yy
        User->>query_rss: 请求某个源的 JSON
        query_rss->>query_rss: 验证为有效用户才继续
        query_rss->>query_rss: 根据 cls_id 能获得到类才继续
        alt 用户是管理员且不在睡眠时间
            query_rss->>crawler: 根据 cls_id 和请求参数 q 走立即请求路径
        else 用户不是管理员
            query_rss->>crawler: 根据 cls_id 和请求参数 q 走缓存路径
        end
        crawler->>crawler: 走抓取源流程
        create participant get_rss
        query_rss->>get_rss: 请求某个源的 RSS
        destroy get_rss
        query_rss-xget_rss: 返回 RSS
        query_rss->>User: 返回 RSS
    end
```

发送信息源的接口（需要权限）

```mermaid
sequenceDiagram
    actor User
    box FastAPI
    participant post_rss
    end
    box source2RSS
    participant crawler
    participant data
    end

    User->>post_rss: 发起请求
    post_rss->>post_rss: 验证用户，为管理员才继续
    alt 访问 /{source_name}/，请求体里是文章列表
        post_rss->>data: 以源名称获取元信息
        data->>post_rss: 返回元信息
        alt 元信息不存在
            post_rss->>post_rss: 组装出默认的元信息
        end
        create participant no_cache_flow
        post_rss->>no_cache_flow: 用特殊抓取器，将元信息和文章列表作为参数传入，走抓取源流程
        destroy no_cache_flow
        post_rss-xno_cache_flow: 返回源名称
    else 以 post 访问根路径，请求体里是源的元信息
        post_rss->>data: 以源名称获取元信息
        data->>post_rss: 返回元信息
        alt 元信息已存在
            post_rss->>User: 返回需要使用 put 更新元信息
        else 元信息不存在
            post_rss->>data: 传入元信息，存储源到元表中
        end
    else 以 put 访问根路径，请求体里是源的元信息
        post_rss->>data: 传入元信息，更新元表中的源
    end
    post_rss->>User: 返回相应信息
```

### 抓取源的时序图


```mermaid
sequenceDiagram
    actor User
    box source2RSS
    participant config
    participant Plugins
    participant crawler
    participant data
    participant uniform_flow
    end

    User->>config: 加载配置
    User->>Plugins: 加载插件
    Plugins->>Plugins: import 插件，插件会注册自身的类
    User->>data: 加载数据
    User->>User: 组装 ClassNameAndParams 列表
    User->>crawler: 传入参数 start_to_crawl

    loop 组装协程
        crawler->>Plugins: 根据类名获得抓取器的类
        Plugins->>crawler: 返回类
        create participant scraper
        crawler->>scraper: 传入参数创建实例
        scraper->>scraper: 查询信息、加锁等
        scraper->>crawler: 返回实例
    end
    crawler->>crawler: 将全部协程放入事件循环

    par 执行类A的协程
        crawler->>uniform_flow: 传递实例，创建多个协程任务
    and 执行类B的协程
        crawler->>uniform_flow: ...
    and 执行类X的协程
        crawler->>uniform_flow: 类之间使用协程并行，类自身多个实例按次序执行
    end

    Note right of uniform_flow: "对于单个协程，其流程如图"
    uniform_flow->>scraper: 获得源的元信息、表名等信息
    scraper->>uniform_flow: 返回信息
    uniform_flow->>data: 确保源在元表中存在
    uniform_flow->>data: 根据指定维度获得最新的文章
    data->>uniform_flow: 返回文章
    alt 文章为空
        uniform_flow->>uniform_flow: 构建参数：flags（获取10个文章）、sequence（优先从新到旧）
    else 文章不为空
        uniform_flow->>uniform_flow: 构建参数：flags（最新文章名称和标志等）、sequence（优先从旧到新）
    end

    uniform_flow->>scraper: 传入参数
    loop 遍历 scraper 返回文章的生成器接口
        uniform_flow->>scraper: 获得文章
        scraper->>uniform_flow: 返回文章
        uniform_flow->>data: 保存文章
    end
    alt 没有返回一篇文章
        uniform_flow->>uniform_flow: 日志打印无更新
    else 返回了文章
        uniform_flow->>data: 获取最新的若干篇
        data->>uniform_flow: 返回文章
        uniform_flow->>uniform_flow: 生成 RSS 格式文本和 JSON 格式数据
        uniform_flow->>data: 缓存数据并保存到硬盘
    end
    uniform_flow->>crawler: 返回源的名称

    destroy scraper
    crawler-xscraper: 调用实例销毁接口释放资源
    crawler->>User: 返回所有实例源的名称

```
