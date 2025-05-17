"""注册插件，以字典存储"""


class Plugins():
    _registry = {}

    @classmethod
    def register(cls, id, cls_instance):
        if cls._registry.get(id):
            raise RuntimeError(f"duplicate scraper class {id}")
        cls._registry[id] = cls_instance

    @classmethod
    def get_plugin_or_none(cls, id):
        return cls._registry.get(id)
