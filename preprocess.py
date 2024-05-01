# 添加命令行参数解析，调用 configHandle，加载插件，调用 dataHandle，实例一些全局类
import argparse

from configHandle import Config

# 创建一个解析器
parser = argparse.ArgumentParser(description="Your script description")
# 添加你想要接收的命令行参数
parser.add_argument('--config', action='append', required=False, 
                    default=['./config_and_data_files/config.yaml', './config_and_data_files/pgm_config.yaml'], 
                    help='Config Files Path')# 解析命令行参数
args = parser.parse_args()
# 将参数值赋给你的变量
configfile = args.config

# 定义所有变量
config = Config(configfile)



import api._v1

plugins = api._v1._private.plugins

# 加载插件
import importlib
import pkgutil

import website_scraper

def iter_namespace(ns_pkg):
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

def load_plugins():
    print("Config enabled web scraper: ", config.enabled_web_scraper)
    # 只导入启用的插件
    enabled_web_scraper = set(config.enabled_web_scraper)
    available_web_scraper = {name for _, name, _ in iter_namespace(website_scraper)}
    print("Process Available web scraper: ", available_web_scraper)
    if "all" not in enabled_web_scraper:
        usable_web_scraper = enabled_web_scraper & available_web_scraper
    else:
        usable_web_scraper = available_web_scraper
    
    print("import plugins: ", end='')
    for usable_web_scraper in enabled_web_scraper & available_web_scraper:
        print(usable_web_scraper, end=',')
        importlib.import_module(usable_web_scraper)
    print()
    
load_plugins()




# 如果前面没出错，可以加载持久化的数据
from dataHandle import Data

data = Data(config)



