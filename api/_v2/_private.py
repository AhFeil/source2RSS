"""注册插件，以字典存储"""
from typing import Iterable, Any
from types import ModuleType
import importlib
import pkgutil

from configHandle import config


class Plugins():
    _registry: dict[str, Any] = {}

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

    @staticmethod
    def iter_namespace(ns_pkg):
        return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

    imported_modules: dict[str, ModuleType] = {}

    @staticmethod
    def load_plugins():
        enabled_web_scraper = set()
        available_web_scraper = set()
        for package_path, module_names in config.enabled_web_scraper.items():
            try:
                module = importlib.import_module(package_path)
            except ModuleNotFoundError:
                print(package_path + " does not exist")
                continue
            enabled_web_scraper |= {f"{package_path}.{module_name}" for module_name in module_names}
            available_web_scraper |= {name for _, name, _ in Plugins.iter_namespace(module)}
        print("Config enabled web scraper: ", enabled_web_scraper)
        print("Process Available web scraper: ", available_web_scraper)

        # 只导入启用的插件
        usable_web_scrapers = enabled_web_scraper & available_web_scraper
        print("import plugins: ")
        for usable_web_scraper in usable_web_scrapers:
            module = importlib.import_module(usable_web_scraper)
            Plugins.imported_modules[usable_web_scraper] = module
            print(usable_web_scraper)
