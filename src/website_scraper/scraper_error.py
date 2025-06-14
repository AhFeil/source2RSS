

class FailtoGet(Exception):
    pass

class ScraperError(Exception):
    pass

class CreateByInvalidParam(ScraperError):
    pass

class CreateByLocked(ScraperError):
    pass
