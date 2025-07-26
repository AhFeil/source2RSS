

class FailtoGet(Exception):
    pass

class ScraperError(Exception):
    pass

class CreateByInvalidParam(ScraperError):
    """
    输入的参数非法

    定期运行不会忽略此异常
    """
    pass

class CreateButRequestFail(ScraperError):
    """
    输入的参数实际没问题，但创建过程中的请求发生错误

    定期运行会忽略此异常，但多次出现会发出提醒
    """
    pass

class CreateByLocked(ScraperError):
    """
    需要的实例，其创建被锁住。
    比如另外一个协程正在使用，不允许有两个相同的实例并发运行。

    定期运行会忽略此异常
    """
    pass
