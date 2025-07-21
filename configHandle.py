import base64
import json
import logging.config
import os
from collections import defaultdict
from contextlib import suppress
from datetime import datetime
from typing import Iterable

import httpx
from ruamel.yaml import YAML, YAMLError

configfile = os.getenv("SOURCE2RSS_CONFIG_FILE", default="config_and_data_files/config.yaml")


# 非线程安全，但在单个事件循环下是协程安全的
class Config:
    yaml = YAML()

    def __init__(self, config_path: str) -> None:
        self.config_path = config_path
        self.reload()
        # 用户不应该考虑的配置，开发者可以改的
        self.rss_dir = "config_and_data_files/rss"
        os.makedirs(self.rss_dir, exist_ok=True)
        self.source_meta = "source_meta"   # 每个来源的元信息放在这个 collection 中
        self.wait_before_close_browser = 180
        self.bili_context = "config_and_data_files/bili_context.json"
        if not os.path.exists(self.bili_context):
            with open(self.bili_context, 'w', encoding="utf-8") as f:
                json.dump({}, f)

    def reload(self) -> None:
        """将配置文件里的参数，赋予单独的变量，方便后面程序调用"""
        configs = self._load_config(self.config_path)
        # 默认无须用户改动的
        logging.config.dictConfig(configs["logging"])
        self.desktop_user_agent = []
        self.mobile_user_agent = []
        self.init_script_path = "" # todo
        data_dir = configs["data_dir"]
        os.makedirs(data_dir, exist_ok=True)
        self.sqlite_uri = f"sqlite:///{data_dir}/source2rss.db"
        self.users_file = f"{data_dir}/users.json"
        # 用户配置
        self.is_production = configs['is_production']
        crawler_default_cfg = configs.get("crawler_default_cfg", {})
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

        self.mongodb_uri = configs.get("mongodb_uri")
        self.mongo_dbname = configs.get("mongo_dbname")

        self.enabled_web_scraper = configs.get('enabled_web_scraper', {})
        self.remote_pub_scraper = configs.get('remote_pub_scraper', {})

        self.ip_or_domain = configs.get('ip_or_domain', "127.0.0.1")
        self.port = configs.get("port", 8536)

        self.query_cache_maxsize = configs.get('query_cache_maxsize', 100)
        self.query_cache_ttl_s = configs.get('query_cache_ttl_s', 3600)
        self.query_username = configs.get('query_username', "vfly2")
        self.query_password = configs.get('query_password', "123456")
        self.query_bedtime = configs.get('query_bedtime', [])

        self.webscraper_profile = configs['webscraper_profile']
        self.ad_html = configs.get("ad_html", "")

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
            return [None]

    def get_amount(self, class_name: str) -> int:
        try:
            return self.webscraper_profile[class_name]["custom_cfg"]["amount_when_firstly_add"]
        except KeyError:
            return self.amount_when_firstly_add

    def in_bedtime(self, class_name: str, hm: str) -> bool:
        """检查 hm 是否在 bedtime 期间，是的话返回真"""
        try:
            bedtime = self.webscraper_profile[class_name]["custom_cfg"]["query_bedtime"]
        except KeyError:
            bedtime = self.query_bedtime
        return any(t[0] <= hm <= t[1] for t in bedtime)

    @staticmethod
    def _load_config(config_path: str) -> dict:
        """加载一个配置文件，从中取出其他配置文件的路径（文件不存在不报错），最终合并得到一份配置，如果其他配置里也带有更多配置的路径，同样加载"""
        config = Config._load_config_file(config_path)
        cfg_files = tuple(config.get("other_configs_path", ()))
        for f in cfg_files:
            with suppress(FileNotFoundError):
                other_config = Config._load_config(f)
                Config._update(config, other_config)
        return config

    @staticmethod
    def _update(config: dict, other_config: dict):
        """
        遍历新的配置中每个键值对，如果在当前配置中不存在，就新增；存在，若是不可变类型，就用新的覆盖；
        若是列表，就在原有的追加；若是字典，就递归。
        """
        for key, val in other_config.items():
            if key not in config:
                config[key] = val
                continue
            if isinstance(val, (bool, int, float, str)):
                config[key] = val
                continue
            if isinstance(val, list):
                config[key].extend(val)
                continue
            if isinstance(val, dict):
                Config._update(config[key], val)
                continue

    @staticmethod
    def _load_config_file(f) -> dict:
        try:
            with open(f, 'r', encoding="utf-8") as fp:
                return Config.yaml.load(fp)
        except YAMLError as e:
            raise YAMLError(f"The config file is illegal as a YAML: {e}")
        except FileNotFoundError:
            raise FileNotFoundError("The config does not exist")


config = Config(os.path.abspath(configfile))

logger = logging.getLogger("post2RSS")

async def post2RSS(title: str, summary: str) -> httpx.Response | None:
    """不引发异常"""
    url = f"http://127.0.0.1:{config.port}/post_src/source2rss_severe_log/"
    timeout = httpx.Timeout(10.0, read=10.0)
    credentials = f"{config.query_username}:{config.query_password}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    data_raw = [{
            "title": title,
            "link": "http://rss.vfly2.com/query_rss/source2rss_severe_log.xml/#" + str(datetime.now().timestamp()),
            "summary": summary,
            "content": summary,
            "pub_time": datetime.now().timestamp()
        }]
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url=url, headers=headers, json=data_raw, timeout=timeout)
        except Exception as e:
            logger.warning(f"exception of post2RSS: {e}")
        else:
            return response
