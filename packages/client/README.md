## 介绍

这是 source2RSS 服务端的 Python 版客户端程序，功能有：
- 向服务端发送文章，从而通过 RSS 跟踪一些情况，比如在程序出错时，使用本客户端发送日志

## 使用

创建客户端实例

```python
from source2RSS_client import S2RProfile, Source2RSSClient

s2r_profile: S2RProfile = {
    "url": "http://127.0.0.1:8536",
    "username": "vfly2",
    "password": "123456",
    "source_name": "source2rss_severe_log",
}
s2r_c = Source2RSSClient.create(s2r_profile)
```

### 发送文章

异步发送

```python
response = await s2r_c.post_article("test_client", "test_client summary")
```

同步发送

```python
response = s2r_c.sync_post_article("test_client", "test_client summary")
```

### 发送测试文章

在第一次使用时，想必都希望能立马看到效果，验证功能是否正常。

在创建客户端实例时，可以让其立刻发送一个文章来进行测试，有两种办法触发这一点：
1. 创建实例时，利用传参控制 `Source2RSSClient.create(s2r_profile, send_test=True)`
2. 添加环境变量，以 Linux 为例 `SOURCE2RSS_CLIENT_SEND_TEST=true`
