

class CrawlError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


class CrawlInitError(CrawlError):
    pass


class CrawlRunError(CrawlError):
    pass
