
使用插件模式，每个抓取器对于 source2RSS 来说都是一个插件，方便自己编写的抓取器集成进项目中，而不需要修改代码。


抓取器的主要职责是根据指定顺序返回文章。


抓取器根据是否重写 `__init__`  方法可以分为**单实例抓取器**和**多实例抓取器**，在实例化类的时候，会自动添加类属性 `is_variety` 进行标记，这两者没什么区别，只不过有些地方可以借助这点简化代码。

所谓单实例抓取器，就比如某个博客的 RSS；所谓多实例抓取器，就比如 B 站 up 动态的 RSS。

多实例抓取器，一定会在实例化时传入不同的参数，因此如果有自己的 `__init__`  方法，而不是从基类继承得到，就认为是多实例的。


## 编写抓取器

如果你要编写自己的抓取器，看明白 [scraper cslrxyz](src/scraper/examples/cslrxyz.py) 就可以动手了。

如果有疑问，可以再看一下基类的代码 [abstract scraper class](src/scraper/scraper) 。


### 抓取器接口

TODO 待写……

有时候一些信息源不一定有时间条目，反而像是章节之类的，这时候可以修改类成员 key4sort = "something"，然后在返回的字典中包含 something 键，这样在生成 RSS 时，就会按照 something 排序。



### 抓取器流程

TODO 待写……


## 注册抓取器

假设自己编写的一个抓取器的类，其所在文件相对项目根目录的路径是 `plugins/source2RSS-scraper/fanqie.py`，注册它只需要在配置文件中，在 `enabled_web_scraper` 里添加该路径：

```yaml
enabled_web_scraper:
  plugins.source2RSS-scraper:
  - fanqie
```

> 其实注册的粒度是文件，而不是抓取器类。换句话说，如果该文件里有两个类，则两个类都会被注册。

注册后，在网页的“用处”页面中就可以看到了，也就可以被定期运行以及主动触发了。


## 自定义抓取器的参数

TODO 待写……
