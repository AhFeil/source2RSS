



def register(cls):
    plugins["static"][cls.title] = cls

def register_d(cls):
    plugins["dynamic"][cls.title] = cls


plugins = {"static": {}, "dynamic": {}}


