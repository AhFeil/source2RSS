import asyncio
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Self

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
                print(f"{source_name} is lack in db")
                access = AccessLevel.SYSTEM
            self._cached_sources[access][source_name] = rss_data

    def get_source_list(self, access: AccessLevel, low_access: AccessLevel=AccessLevel.NONE, except_access: tuple[AccessLevel, ...]=tuple()) -> list[tuple[str, str]]:
        """返回 access 到 low_access 之间的所有源的表名和展示名， 不包含 low_access"""
        source_list = []
        for i in filter(lambda x : x not in except_access, range(access, low_access, -1)):
            for k, v in self._cached_sources[i].items():
                source_list.append((k, v.json["source_info"]["name"]))
        return source_list

    def get_source_or_None(self, source_name: str, access: AccessLevel, except_access: tuple[AccessLevel, ...]=tuple()) -> RSSData | None:
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
    """一个 agent 同一时间只能处理一个任务"""
    sid: str
    name: str
    scrapers: list[str]
    sio: AsyncServer
    pending_futures: dict[str, asyncio.Future]
    busy: bool = False

    async def __aenter__(self) -> tuple[Callable[[str, str, dict], Awaitable[None]], Callable[[str], Awaitable[dict | None]]] | tuple[None, None]:
        if self.busy:
            return None, None
        self.busy = True

        async def send(msg_id: str, event: str, data: dict):
            if not data.get("over"):
                fut = asyncio.get_running_loop().create_future()
                self.pending_futures[msg_id] = fut
            data["msg_id"] = msg_id
            await self.sio.emit(event, data, to=self.sid)

        async def recv(msg_id: str) -> dict | None:
            fut = self.pending_futures.get(msg_id)
            if not fut:
                return

            try:
                reply = await asyncio.wait_for(fut, timeout=180)
            except asyncio.TimeoutError:
                self.pending_futures.pop(msg_id, None)
                return
            if reply.get("over"):
                self.pending_futures.pop(msg_id, None)
                return
            return reply

        return send, recv

    async def __aexit__(self, exc_type, exc, tb):
        self.busy = False


@dataclass
class Agents:
    _agents: dict[str, Agent]
    _agents_name: dict[str, str]
    _supported_scrapers: defaultdict[str, set[str]] # 存储支持某抓取器的全部远端
    _logger: logging.Logger

    __slot__ = ("_agents", "_agents_name", "_supported_scrapers", "_logger")

    @classmethod
    def create(cls) -> Self:
        return cls(
            _agents={},
            _agents_name={},
            _supported_scrapers=defaultdict(set),
            _logger=logging.getLogger("Agents"),
        )

    def register(self, sid: str, name: str, scrapers: list[str], sio: AsyncServer):
        if self._agents.get(sid):
            self._logger.info("replicate agent, both sid are %s, name is %s", sid, name)
            return
        self._agents[sid] = Agent(sid, name, scrapers, sio, {})
        self._agents_name[sid] = name
        # TODO 校验外部数据
        for scraper in scrapers:
            self._supported_scrapers[scraper].add(sid)
        if self._agents_name.get(name):
            self._logger.debug("replicate agent, sid is %s, both name are %s", sid, name)
        self._logger.info("远端注册成功: %s", name)

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

    def get(self, cls_id: str) -> tuple[Agent, ...]:
        if agents_sid := self._supported_scrapers.get(cls_id):
            return tuple(self._agents[sid] for sid in agents_sid)
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
            with open(config.users_file, 'r', encoding="utf-8") as f:
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
