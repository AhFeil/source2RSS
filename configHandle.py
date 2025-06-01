import sys
import os
import json
import logging.config
from typing import Generator, Iterable
from collections import defaultdict

from ruamel.yaml import YAML, YAMLError


configfile = os.getenv("SOURCE2RSS_CONFIG_FILE", default='config_and_data_files/config.yaml')
pgm_configfile = os.getenv("SOURCE2RSS_PGM_CONFIG_FILE", default='config_and_data_files/pgm_config.yaml')


class Config:
    def __init__(self, configs_path: Iterable[str]) -> None:
        self.yaml = YAML()
        self.configs_path = tuple(configs_path)
        self.reload()

        # 用户不应该考虑的配置，开发者可以改的
        self.sqlite_uri = "sqlite:///config_and_data_files/source2rss.db"
        self.rss_dir = "config_and_data_files/rss"
        os.makedirs(self.rss_dir, exist_ok=True)
        self.source_meta = "source_meta"   # 每个来源的元信息放在这个 collection 中
        self.run_test_every_seconds = 30
        self.bili_context = "config_and_data_files/bili_context.json"
        if not os.path.exists(self.bili_context):
            with open(self.bili_context, 'w', encoding="utf-8") as f:
                json.dump({}, f)

    def _load_config(self) -> Generator[dict, None, None]:
        """定义如何加载配置文件"""
        for f in self.configs_path:
            try:
                with open(f, "r", encoding='utf-8') as fp:
                    configs = self.yaml.load(fp)
                yield configs
            except YAMLError as e:
                sys.exit(f"The config file is illegal as a YAML: {e}")
            except FileNotFoundError:
                sys.exit("The config does not exist")

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
        crawler_default_cfg = user_configs.get("crawler_default_cfg", {})
        run_everyday_at = crawler_default_cfg.get("run_everyday_at", "06:00")
        self.run_everyday_at = [run_everyday_at] if isinstance(run_everyday_at, str) else run_everyday_at
        self.WAIT = crawler_default_cfg.get("WAIT", 1800)
        self.amount_when_firstly_add = crawler_default_cfg.get("amount_when_firstly_add", 10)
        self.image_root = crawler_default_cfg.get("image_root", "config_and_data_files/images")
        os.makedirs(self.image_root, exist_ok=True)
        self.timezone = crawler_default_cfg.get("timezone", "Asia/Shanghai")
        self.max_opening_context = crawler_default_cfg.get("max_opening_context", 1)
        if self.max_opening_context <= 0:
            self.max_opening_context = 1

        self.mongodb_uri = user_configs.get("mongodb_uri")
        self.mongo_dbname = user_configs.get("mongo_dbname")

        enabled_web_scraper = user_configs.get('enabled_web_scraper', [])
        self.enabled_web_scraper = [f"src.{scraper}" for scraper in enabled_web_scraper]
        self.remote_pub_scraper = user_configs.get('remote_pub_scraper', {})

        self.query_cache_maxsize = user_configs.get('query_cache_maxsize', 100)
        self.query_cache_ttl_s = user_configs.get('query_cache_ttl_s', 3600)
        self.query_username = user_configs.get('query_username', "vfly2")
        self.query_password = user_configs.get('query_password', "123456")

        self.webscraper_profile = user_configs['webscraper_profile']

    def get_schedule(self, class_name: str) -> list:
        try:
            sche = self.webscraper_profile[class_name]["custom_cfg"]["run_everyday_at"]
            return [sche] if isinstance(sche, str) else sche
        except KeyError:
            return self.run_everyday_at

    def get_schedule_and_cls_names(self, class_names: Iterable[str]) -> dict[str, list[str]]:
        """返回每个时间点需要执行的类的名称"""
        points_cls = defaultdict(list)
        for cls_name in class_names:
            for p in self.get_schedule(cls_name):
                points_cls[p].append(cls_name)
        return points_cls

    def get_params(self, class_name: str) -> list:
        try:
            return self.webscraper_profile[class_name]["cls_init_params"]
        except KeyError:
            return []

    def get_amount(self, class_name: str) -> int:
        try:
            return self.webscraper_profile[class_name]["custom_cfg"]["amount_when_firstly_add"]
        except KeyError:
            return self.amount_when_firstly_add


absolute_configfiles = map(lambda x:os.path.join(os.getcwd(), x), (configfile, pgm_configfile))
config = Config(absolute_configfiles)
