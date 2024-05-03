



def register(cls):
    plugins["static"][cls.title] = cls

def register_d(cls):
    plugins["dynamic"][cls.title] = cls

def register_c(cls):
    plugins["chapter_mode"][cls.title] = cls

plugins = {"static": {}, "dynamic": {}, "chapter_mode": {}}


