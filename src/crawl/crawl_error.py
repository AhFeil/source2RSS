

class CrawlError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


class CrawlRepeatError(CrawlError):
    """将要创建的实例，已经有一个相同的在运行"""
    def __init__(self, message: str):
        super().__init__(466, message)


class CrawlInitError(CrawlError):
    """创建抓取器实例时出错"""
    pass


class CrawlRunError(CrawlError):
    """抓取器实例运行时出错"""
    pass
