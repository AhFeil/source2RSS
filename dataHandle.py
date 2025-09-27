import asyncio
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from socketio import AsyncServer

from configHandle import config
from src.data import DatabaseIntf
from src.scraper import AccessLevel


@dataclass
class RSSData:
    xml: str
    json: dict


class RSSCache:
    """内存里缓存的RSS数据"""
    def __init__(self, rss_dir: str, db_intf: DatabaseIntf) -> None:
        self.rss_dir = Path(rss_dir)
        self._cached_sources: list[dict[str, RSSData]] = [{} for _ in range(AccessLevel.ADMIN + 1)]
        for source_name, rss_data in RSSCache._load_files_to_dict(self.rss_dir).items():
            src_meta = db_intf.get_source_info(source_name)
            if src_meta:
                access = src_meta["access"]
                rss_data.json["source_info"] = src_meta
            else:
                print(f"{source_name} is lack in db")  # noqa: T201
                access = AccessLevel.SYSTEM
            self._cached_sources[access][source_name] = rss_data

    def get_source_list(self, access: AccessLevel, low_access: AccessLevel=AccessLevel.NONE, except_access: tuple[AccessLevel, ...] = ()) -> list[tuple[str, str]]:
        """返回 access 到 low_access 之间的所有源的表名和展示名， 不包含 low_access"""
        source_list = []
        for i in filter(lambda x : x not in except_access, range(access, low_access, -1)):
            for k, v in self._cached_sources[i].items():
                source_list.append((k, v.json["source_info"]["name"]))
        return source_list

    def get_source_or_None(self, source_name: str, access: AccessLevel, except_access: tuple[AccessLevel, ...] = ()) -> RSSData | None:
        """当源存在且有权限返回源"""
        for i in filter(lambda x : x not in except_access, range(access, AccessLevel.NONE, -1)):
            if rss_data := self._cached_sources[i].get(source_name):
                return rss_data

    def set_rss(self, source_name: str, rss: bytes, rss_json: dict, access: AccessLevel):
        """将RSS源表名称和RSS内容映射，如果是单例，还将类名和RSS内容映射"""
        rss_data = RSSData(rss.decode(), rss_json)
        self._cached_sources[access][source_name] = rss_data
        rss_filepath = self.rss_dir / (source_name + ".xml")
        with open(rss_filepath, 'wb') as rss_file:   # todo 退出时保存一次
            rss_file.write(rss)

    def rss_is_absent(self, source_name: str) -> bool:
        return all(source_name not in self._cached_sources[access] for access in AccessLevel)


    def get_source_readable_name(self, table_name: str, access: AccessLevel=AccessLevel.USER, low_access: AccessLevel=AccessLevel.NONE) -> str:
        """根据 table name 返回可读的源名称，如果找不到就返回 table name"""
        for i in range(access, low_access, -1):
            if table_name in self._cached_sources[i]:
                return self._cached_sources[i][table_name].json["source_info"]["name"]
        return table_name

    @staticmethod
    def _load_files_to_dict(path: Path) -> dict[str, RSSData]:
        file_dict = {}
        for file_path in path.iterdir():
            if file_path.is_file():
                file_content = file_path.read_text(encoding='utf-8')
                rss_json = {"source_info": {"name": file_path.stem}, "detail": "RSS json is missed in cache"}
                rss_data = RSSData(file_content, rss_json)
                file_dict[file_path.stem] = rss_data
        return file_dict


@dataclass
class Agent:
    sid: str
    name: str
    scrapers: list[str]
    sio: AsyncServer
    pending_futures: dict[str, asyncio.Future]


@dataclass
class D_Agent:
    name: str
    scrapers: list[str]
    uri: str


@dataclass
class Agents:
    _agents: dict[str, Agent]      # sid -> agent
    _agents_name: dict[str, str]   # sid -> name
    _d_agents: dict[str, D_Agent]  # name -> agent
    _supported_scrapers: defaultdict[str, set[str]] # 存储支持某抓取器的全部远端 sid/name
    _logger: logging.Logger

    __slots__ = ("_agents", "_agents_name", "_d_agents", "_supported_scrapers", "_logger")

    @classmethod
    def create(cls) -> Self:
        d_agents = {}
        supported_scrapers = defaultdict(set)
        for agent in config.known_agents:
            if agent.get("connect_method") == "direct_websocket":
                name, scrapers, uri = agent["name"], agent["enabled_scrapers"], agent["agent_uri"]
                d_agents[name] = D_Agent(name, scrapers, uri)
                for scraper in scrapers:
                    supported_scrapers[scraper].add(name)
        return cls(
            _agents={},
            _agents_name={},
            _d_agents=d_agents,
            _supported_scrapers=supported_scrapers,
            _logger=logging.getLogger("Agents"),
        )

    def register(self, sid: str, name: str, scrapers: list[str], sio: AsyncServer) -> tuple[bool, str]:
        if self._agents.get(sid):
            self._logger.info("replicate agent, both sid are %s, name is %s", sid, name)
            return False, f"replicate agent, both sid are {sid}, name is {name}"
        self._agents[sid] = Agent(sid, name, scrapers, sio, {})
        self._agents_name[sid] = name
        # TODO 校验外部数据
        for scraper in scrapers:
            self._supported_scrapers[scraper].add(sid)
        if self._agents_name.get(name):
            self._logger.debug("replicate agent, sid is %s, both name are %s", sid, name)
        self._logger.info("远端注册成功: %s", name)
        return True, ""

    def delete(self, sid: str):
        if self._agents.get(sid):
            agent = self._agents.pop(sid)
            name = self._agents_name.pop(sid)
            for scraper in agent.scrapers:
                self._supported_scrapers[scraper].discard(sid)
            self._logger.info("远端已删除: %s", name)
            # TODO 中止其下所有 future

    def get_agent(self, sid: str) -> Agent | None:
        return self._agents.get(sid)

    def get(self, cls_id: str) -> tuple[D_Agent | Agent, ...]:
        if agents_sid := self._supported_scrapers.get(cls_id):
            return tuple(self._d_agents.get(sid) or self._agents[sid] for sid in agents_sid)
        return ()

# 非线程安全，但在单个事件循环下是协程安全的
class Data:
    def __init__(self, config) -> None:
        self.config = config
        self.logger = logging.getLogger("dataHandle")

        # 从文件里加载用户数据
        self._users = {"invite_code": None, "left_count": 0, "users": []}
        if not os.path.exists(config.users_file):
            with open(config.users_file, 'w', encoding="utf-8") as f:
                json.dump(self._users, f)
        else:
            with open(config.users_file, encoding="utf-8") as f:
                self._users = json.load(f)

        # DB
        if config.mongodb_uri is not None:
            from src.data import MongodbConnInfo, MongodbIntf
            info = MongodbConnInfo(config.mongodb_uri, config.mongo_dbname, config.source_meta)
            self.db_intf: DatabaseIntf = MongodbIntf.connect(info)
        else:
            from src.data import SQliteConnInfo, SQliteIntf
            info = SQliteConnInfo(config.sqlite_uri)
            self.db_intf: DatabaseIntf = SQliteIntf.connect(info)

        self.rss_cache = RSSCache(config.rss_dir, self.db_intf)
        self.agents = Agents.create()

    def get_users_and_etc(self) -> dict:
        return self._users

    def save_users_and_etc(self, code, count, users: list):
        self._users["invite_code"] = code
        self._users["left_count"] = count
        self._users["users"] = users
        json_string = json.dumps(self._users, ensure_ascii=False, indent=4)
        with open(config.users_file, 'w', encoding="utf-8") as f:
            f.write(json_string)

data = Data(config)
