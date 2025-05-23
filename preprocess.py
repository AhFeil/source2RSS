"""
添加命令行参数解析，调用 configHandle，加载插件，调用 dataHandle，实例一些全局类
"""
import os
from configHandle import Config

configfile = os.getenv("SOURCE2RSS_CONFIG_FILE", default='config_and_data_files/config.yaml')
pgm_configfile = os.getenv("SOURCE2RSS_PGM_CONFIG_FILE", default='config_and_data_files/pgm_config.yaml')
absolute_configfiles = map(lambda x:os.path.join(os.getcwd(), x), (configfile, pgm_configfile))
config = Config(absolute_configfiles)


from api._v2 import Plugins
import api._v1
plugins = api._v1._private.plugins

# 加载插件
import importlib
import pkgutil

from src import website_scraper
from src import dynamic_web_scraper

def iter_namespace(ns_pkg):
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

def load_plugins():
    enabled_web_scraper = set(config.enabled_web_scraper)
    available_web_scraper = {name for _, name, _ in iter_namespace(website_scraper)} | {name for _, name, _ in iter_namespace(dynamic_web_scraper)}
    print("Config enabled web scraper: ", config.enabled_web_scraper)
    print("Process Available web scraper: ", available_web_scraper)

    # 只导入启用的插件
    usable_web_scrapers = enabled_web_scraper & available_web_scraper
    print("import plugins: ")
    for usable_web_scraper in usable_web_scrapers:
        importlib.import_module(usable_web_scraper)
        print(usable_web_scraper)


load_plugins()


# 如果前面没出错，可以加载持久化的数据
from dataHandle import Data

data = Data(config)
