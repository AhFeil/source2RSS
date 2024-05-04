



def register(cls):
    plugins["static"].append(cls)

def register_c(cls):
    plugins["chapter_mode"].append(cls)

plugins = {"static": [], "chapter_mode": []}


