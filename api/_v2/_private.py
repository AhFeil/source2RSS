"""注册插件，以字典存储"""
from typing import Iterable


class Plugins():
    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, id, cls_instance):
        if cls._registry.get(id):
            raise RuntimeError(f"duplicate scraper class {id}")
        cls._registry[id] = cls_instance

    @classmethod
    def get_plugin_or_none(cls, id):
        return cls._registry.get(id)

    @classmethod
    def get_all_id(cls) -> Iterable[str]:
        return cls._registry.keys()

    @classmethod
    def get_all_cls(cls) -> Iterable[type]:
        return cls._registry.values()
