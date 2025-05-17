import sys
import os
import json
import logging.config
from typing import Generator, Any

from ruamel.yaml import YAML, YAMLError


class Config:
    def __init__(self, configs_path: list[str]) -> None:
        self.yaml = YAML()
        self.configs_path = configs_path
        self.reload()

        # 用户不应该考虑的配置，开发者可以改的
        self.rss_dir = "config_and_data_files/rss"
        os.makedirs(self.rss_dir, exist_ok=True)
        self.source_meta = "source_meta"   # 每个来源的元信息放在这个 collection 中
        self.run_test_every_seconds = 10
        self.bili_context = "config_and_data_files/bili_context.json"
        if not os.path.exists(self.bili_context):
            with open(self.bili_context, 'w', encoding="utf-8") as f:
                json.dump({}, f)

    def _load_config(self) -> Generator[dict, Any, Any]:
        """定义如何加载配置文件"""
        for f in self.configs_path:
            try:
                with open(f, "r", encoding='utf-8') as fp:
                    configs = self.yaml.load(fp)
                yield configs
            except YAMLError as e:
                sys.exit(f"The config file is illegal as a YAML: {e}")
            except FileNotFoundError:
                sys.exit(f"The config does not exist")
    
    def reload(self) -> None:
        """将配置文件里的参数，赋予单独的变量，方便后面程序调用"""
        for i, configs in enumerate(self._load_config()):
            if configs.get("user_configuration"):
                user_configs = configs
            elif configs.get("program_configuration"):
                program_configs = configs
            else:
                sys.exit(f"{self.configs_path[i]} unknow configuration, lacking key for identify")

        # 默认无须用户改动的
        logging.config.dictConfig(program_configs["logging"])
        self.desktop_user_agent = program_configs["desktop_user_agent"]
        self.mobile_user_agent = program_configs["mobile_user_agent"]
        self.init_script_path = program_configs["init_script_path"]
        self.screenshot_root = program_configs["screenshot_root"]

        # 用户配置
        self.is_production = user_configs['is_production']
        run_everyday_at = user_configs.get("run_everyday_at", "06:00")
        self.run_everyday_at = [run_everyday_at] if isinstance(run_everyday_at, str) else run_everyday_at
        self.timezone = user_configs.get('timezone')
        self.WAIT = user_configs.get("WAIT", 1800) if self.is_production else 1
        self.mongodb_uri = user_configs['mongodb_uri']
        self.mongo_dbname = user_configs['mongo_dbname']

        enabled_web_scraper = user_configs.get('enabled_web_scraper', [])
        self.enabled_web_scraper = [f"src.{scraper}" for scraper in enabled_web_scraper]
        self.remote_pub_scraper = user_configs.get('remote_pub_scraper', {})
        
        self.image_root = user_configs['image_root']
        os.makedirs(self.image_root, exist_ok=True)
    
        self.cls_init_params = user_configs['cls_init_params']

    def get_params(self, class_name: str) -> list:
        return self.cls_init_params[class_name]
