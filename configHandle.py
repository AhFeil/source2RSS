import logging.config
import os
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from briefconf import BriefConfig

from client.src.source2RSS_client import S2RProfile, Source2RSSClient

configfile = os.getenv("SOURCE2RSS_CONFIG_FILE", default="config_and_data_files/config.yaml")
merged_config = os.getenv("SOURCE2RSS_MERGED_CONFIG", default="")


@dataclass(slots=True)
class Config(BriefConfig):
    # 默认无须用户改动的
    data_dir: str
    sqlite_uri: str
    users_file: str

    # 用户配置
    run_everyday_at: list[str]
    WAIT: int
    amount_when_firstly_add: int
    max_of_rss_items: int
    timezone: str
    max_opening_context: int
    prefer_agent: str

    mongodb_uri: str | None
    mongo_dbname: str | None

    enabled_web_scraper: dict[str, str]
    remote_pub_scraper: dict[str, str]

    query_cache_maxsize: int
    query_cache_ttl_s: int
    query_username: str
    query_password: str
    query_bedtime: list[str]

    scraper_profile_file: list[str]
    scraper_profile: dict # 运行时可以改变

    port: int
    s2r_c: Source2RSSClient | None

    enable_agent_server: bool
    known_agents: list[dict[str, Any]]

    # 用户不应该考虑的配置，开发者可以改的
    rss_dir: str = "config_and_data_files/rss"
    source_meta: str = "source_meta"   # 存储源的元信息的表的名称
    wait_before_close_browser: int = 180
    refractory_period: int = 60 # 当一个抓取器实例被创建后的一段时间，不接受同一种实例的创建，避免无效的重复
    init_script_path: str = "" # TODO
    _crawl_schedules: tuple[tuple[str, tuple], ...] = () # 运行时可以改变

    @classmethod
    def load(cls, config_path: str) -> Self:
        configs = cls._load_config(config_path)
        if merged_config:
            Path(merged_config).write_text(BriefConfig._dump(configs))  # noqa: SLF001
        logging.config.dictConfig(configs["logging"])

        data_dir = configs.get("data_dir", "config_and_data_files")
        crawler_default_cfg: dict = configs.get("crawler_default_cfg", {})
        run_everyday_at = crawler_default_cfg.get("run_everyday_at", "06:00")

        max_opening_context = crawler_default_cfg.get("max_opening_context", 1)
        if max_opening_context <= 0:
            max_opening_context = 1

        scraper_profile_file = configs.get("scraper_profile", [])

        query_username = configs.get("query_username", "vfly2")
        query_password = configs.get("query_password", "123456")
        port = configs.get("port", 8536)
        if configs.get("enable_s2r_c"):
            s2r_profile: S2RProfile = {
                "ip_or_domain": "127.0.0.1",
                "port": port,
                "username": query_username,
                "password": query_password,
                "source_name": "source2rss_severe_log",
            }
            s2r_c = Source2RSSClient.create(s2r_profile)
        else:
            s2r_c = None

        config = cls(
            data_dir=data_dir,
            sqlite_uri=f"sqlite:///{data_dir}/source2rss.db",
            users_file=f"{data_dir}/users.json",

            run_everyday_at=[run_everyday_at] if isinstance(run_everyday_at, str) else run_everyday_at,
            WAIT=crawler_default_cfg.get("WAIT", 1800),

            amount_when_firstly_add=crawler_default_cfg.get("amount_when_firstly_add", 10),
            max_of_rss_items=crawler_default_cfg.get("max_of_rss_items", 50),
            timezone=crawler_default_cfg.get("timezone", "Asia/Shanghai"),
            max_opening_context=max_opening_context,
            prefer_agent=crawler_default_cfg.get("prefer_agent", "self"),
            mongodb_uri=configs.get("mongodb_uri"),
            mongo_dbname=configs.get("mongo_dbname"),
            enabled_web_scraper=configs.get('enabled_web_scraper', {}),
            remote_pub_scraper=configs.get('remote_pub_scraper', {}),
            query_cache_maxsize=configs.get('query_cache_maxsize', 100),
            query_cache_ttl_s=configs.get('query_cache_ttl_s', 3600),
            query_username=query_username,
            query_password=query_password,
            query_bedtime=configs.get('query_bedtime', []),
            scraper_profile_file=scraper_profile_file,
            scraper_profile=cls.load_scraper_profile(scraper_profile_file),
            port=port,
            s2r_c=s2r_c,
            enable_agent_server=configs.get("enable_agent_server", False),
            known_agents=configs.get("known_agents", []),
        )
        config.prepare()
        return config

    def prepare(self) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.rss_dir, exist_ok=True)

    async def post2RSS(self, title: str, summary: str):
        if self.s2r_c:
            await self.s2r_c.post_article(title, summary)

    def is_a_known_agent(self, name: str) -> bool:
        return name in (agent["name"] for agent in self.known_agents)

    def get_scraper_profile(self, index: int) -> str:
        if 0 <= index < len(self.scraper_profile_file):
            with open(self.scraper_profile_file[index], encoding="utf-8") as f:
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

    @classmethod
    def load_scraper_profile(cls, scraper_profile_file: list[str]):
        scraper_profile = {}
        for sp_file in scraper_profile_file:
            scraper_profile |= cls._load_config_file(sp_file)
        return scraper_profile


config = Config.load(os.path.abspath(configfile))
