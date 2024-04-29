import sys
import logging.config

from ruamel.yaml import YAML, YAMLError


class Config:
    def __init__(self, configs_path='./configs.yaml') -> None:
        self.yaml = YAML()
        self.configs_path = configs_path
        self.reload()

        # 用户可以不管，开发者可以改的
        self.source_meta = "source_meta"   # 每个来源的元信息放在这个 collection 中
        self.run_test_every_seconds = 10

    def _load_config(self) -> dict:
        """定义如何加载配置文件"""
        try:
            with open(self.configs_path, "r", encoding='utf-8') as fp:
                configs = self.yaml.load(fp)
            return configs
        except YAMLError as e:
            sys.exit(f"The config file is illegal as a YAML: {e}")
        except FileNotFoundError:
            sys.exit(f"The config does not exist")
    
    def reload(self) -> None:
        """将配置文件里的参数，赋予单独的变量，方便后面程序调用"""
        configs = self._load_config()
        logging.config.dictConfig(configs["logging"])
        self.is_production = configs['is_production']
        self.run_everyday_at = configs.get("run_everyday_at", "06:00")
        self.WAIT = configs.get("WAIT", 1800) if self.is_production else 1

        self.mongodb_uri = configs['mongodb_uri']
        self.mongo_dbname = configs['mongo_dbname']

        self.enabled_web_scraper = configs.get('enabled_web_scraper', "all")
        self.rss_dir = configs['rss_dir']
        self.domain_url = configs['domain_url']
        