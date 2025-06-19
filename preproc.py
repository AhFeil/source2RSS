# ruff: noqa: E402
"""
添加命令行参数解析，调用 configHandle，加载插件，调用 dataHandle，实例一些全局类
"""
from api._v2 import Plugins
from configHandle import config

# 加载插件
Plugins.load_plugins()


# 如果前面没出错，可以加载持久化的数据
from dataHandle import data

__all__ = ["config", "Plugins", "data"]
