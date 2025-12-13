# ruff: noqa: E402
"""
调用 config_handle，加载插件，调用 data_handle，实例一些全局类
"""
from api._v2 import Plugins
from config_handle import config

# 加载插件
Plugins.load_plugins()


# 如果前面没出错，可以加载持久化的数据
from data_handle import data

__all__ = ["config", "Plugins", "data"]
