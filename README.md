# source2RSS

将接收到的文章元信息以 RSS 格式保存为文件，可以使用 Nginx 公开访问。

为不提供 RSS 的网站编写程序提供 RSS




可以选择在一台电脑上只运行 crawler，将数据发给 source2RSS API ，让它生成 RSS












通过插件架构，方便添加新网站的刮削器

## 插件的接口

起码要实现这样的生成器：返回文章，按照网站展示的顺序

比如博客，文章顺序就是首页从上到下，第二页等等。基本都是按照发布时间排序，从新到旧，但也有从旧到新的，比如小说

对于从新到旧，要有一个方法，名为 article_newer_than(datetime) 或 chapter_greater_than(id) 类似的，前者按照发布时间排序，后者安装固有元信息排，比如章节数。这样在生成 RSS 时，从最新的开始，一直到指定的 flag 结束

反过来，对于从旧到新，这种不适合 RSS，必须想办法再实现一个方法输出从新到旧，


还需要为第一次，编写一个函数，返回数据，如果按照默认的，从新到旧全部获取一遍，对于有几千个等很多的，对于 RSS 没必要，也不安全。


三个外部调用时的接口

```python
    async def first_add(self, amount: int = 10):
        """接口.第一次添加时，要调用的接口"""
        # 获取最新的 10 条，
        i = 0
        async for a in CSLRXYZ.parse():
            if i < amount:
                i += 1
                yield a
            else:
                return

    def get_source_info(self):
        """接口.返回元信息，主要用于 RSS"""
        return CSLRXYZ.source_info

    def get_table_name(self):
        """接口.返回元信息，主要用于 RSS"""
        return WebsiteScraper.title
        
    async def get_new(self, datetime_):
        """接口.第一次添加时，要调用的接口"""
        async for a in self.article_newer_than(datetime_):
            yield a
```