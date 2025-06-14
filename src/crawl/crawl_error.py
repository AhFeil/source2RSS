

class CrawlError(Exception):
    pass

class CrawlInitError(CrawlError):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code

class CrawlRunError(CrawlError):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
