import logging.config
import os
from collections import defaultdict
from contextlib import suppress
from typing import Iterable

from ruamel.yaml import YAML, YAMLError

from client.src.source2RSS_client import S2RProfile, Source2RSSClient

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
        self.source_meta = "source_meta"   # 源的元信息的表名
        self.wait_before_close_browser = 180
        self._crawl_schedules: tuple[tuple[str, tuple], ...] = tuple()

    def reload(self) -> None:
        """将配置文件里的参数，赋予单独的变量，方便后面程序调用"""
        configs = Config._load_config(self.config_path)
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
        self.max_of_rss_items = crawler_default_cfg.get("max_of_rss_items", 50)
        self.timezone = crawler_default_cfg.get("timezone", "Asia/Shanghai")
        self.max_opening_context = crawler_default_cfg.get("max_opening_context", 1)
        if self.max_opening_context <= 0:
            self.max_opening_context = 1
        self.prefer_agent = crawler_default_cfg.get("prefer_agent", "self")

        self.mongodb_uri = configs.get("mongodb_uri")
        self.mongo_dbname = configs.get("mongo_dbname")

        self.enabled_web_scraper = configs.get('enabled_web_scraper', {})
        self.remote_pub_scraper = configs.get('remote_pub_scraper', {})

        self.query_cache_maxsize = configs.get('query_cache_maxsize', 100)
        self.query_cache_ttl_s = configs.get('query_cache_ttl_s', 3600)
        self.query_username = configs.get('query_username', "vfly2")
        self.query_password = configs.get('query_password', "123456")
        self.query_bedtime = configs.get('query_bedtime', [])

        self.scraper_profile_file = configs.get("scraper_profile", [])
        self.scraper_profile = self.load_scraper_profile(self.scraper_profile_file)
        self.ad_html = configs.get("ad_html", "")

        self.enable_s2r_c = configs.get("enable_s2r_c")
        self.port = configs.get("port", 8536)
        if self.enable_s2r_c:
            s2r_profile: S2RProfile = {
                "ip_or_domain": "127.0.0.1",
                "port": self.port,
                "username": self.query_username,
                "password": self.query_password,
                "source_name": "source2rss_severe_log",
            }
            self.s2r_c = Source2RSSClient.create(s2r_profile)
        self.enable_agent_server = configs.get("enable_agent_server", False)
        self.known_agents = configs.get("known_agents", [])
        self.as_agent = configs.get("as_agent", {}) # 默认不启用

    async def post2RSS(self, title: str, summary: str):
        if self.enable_s2r_c:
            await self.s2r_c.post_article(title, summary)

    def is_a_known_agent(self, name: str) -> bool:
        return name in (agent["name"] for agent in self.known_agents)

    def get_scraper_profile(self, index: int) -> str:
        if 0 <= index < len(self.scraper_profile_file):
            with open(self.scraper_profile_file[index], 'r', encoding="utf-8") as f:
                return f.read()
        return "You doesn't set the scraper profile file"

    def set_scraper_profile(self, profile: str, index: int):
        if 0 <= index < len(self.scraper_profile_file):
            self.scraper_profile = self.load_scraper_profile(self.scraper_profile_file)
            with open(self.scraper_profile_file[index], 'w', encoding="utf-8") as f:
                f.write(profile)

    def get_usage_cache(self) -> int:
        return sum(len(scrapers) for _, scrapers in self.enabled_web_scraper.items())

    def get_schedule(self, class_name: str) -> list:
        try:
            sche = self.scraper_profile[class_name]["custom_cfg"]["run_everyday_at"]
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

    def set_crawl_schedules(self, crawl_schedules: dict[str, list]):
        m = [(k, tuple(v)) for k, v in crawl_schedules.items()]
        m.sort(key=lambda x : x[0])
        self._crawl_schedules = tuple(m)

    def get_crawl_schedules(self) -> tuple[tuple[str, tuple], ...]:
        return self._crawl_schedules

    def get_prefer_agent(self, class_name: str) -> str:
        try:
            return self.scraper_profile[class_name]["custom_cfg"]["prefer_agent"]
        except KeyError:
            return self.prefer_agent

    def get_params(self, class_name: str) -> list:
        try:
            return self.scraper_profile[class_name]["cls_init_params"]
        except KeyError:
            return [[]]

    def get_amount(self, class_name: str) -> int:
        try:
            return self.scraper_profile[class_name]["custom_cfg"]["amount_when_firstly_add"]
        except KeyError:
            return self.amount_when_firstly_add

    def get_max_rss_items(self, class_name: str) -> int:
        try:
            return self.scraper_profile[class_name]["custom_cfg"]["max_of_rss_items"]
        except KeyError:
            return self.max_of_rss_items

    def in_bedtime(self, class_name: str, hm: str) -> bool:
        """检查 hm 是否在 bedtime 期间，是的话返回真"""
        try:
            bedtime = self.scraper_profile[class_name]["custom_cfg"]["query_bedtime"]
        except KeyError:
            bedtime = self.query_bedtime
        return any(t[0] <= hm <= t[1] for t in bedtime)

    @staticmethod
    def load_scraper_profile(scraper_profile_file: list[str]):
        scraper_profile = {}
        for sp_file in scraper_profile_file:
            scraper_profile |= Config._load_config_file(sp_file)
        return scraper_profile

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
    def _load_config_file(f: str) -> dict:
        try:
            with open(f, 'r', encoding="utf-8") as fp:
                return Config.yaml.load(fp)
        except YAMLError as e:
            raise YAMLError(f"The config file is illegal as a YAML: {e}")
        except FileNotFoundError:
            raise FileNotFoundError("The config does not exist")


config = Config(os.path.abspath(configfile))
