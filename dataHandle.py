import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

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
        self._cached_sources = [{} for _ in range(AccessLevel.ADMIN + 1)]
        for source_name, rss_data in RSSCache._load_files_to_dict(self.rss_dir).items():
            src_meta = db_intf.get_source_info(source_name)
            if src_meta:
                access = src_meta["access"]
            else:
                print(f"{source_name} is lack in db")
                access = AccessLevel.SYSTEM
            self._cached_sources[access][source_name] = rss_data

    def get_source_list(self, access: AccessLevel, low_access: AccessLevel=AccessLevel.NONE, except_access: tuple[AccessLevel, ...]=tuple()) -> list[str]:
        """返回 access 及其下的所有源， 但不包含 low_access 及其以下的"""
        source_list = []
        for i in filter(lambda x : x not in except_access, range(access, low_access, -1)):
            source_list.extend(self._cached_sources[i].keys())
        return source_list

    def get_source_or_None(self, source_name: str, access: AccessLevel, except_access: tuple[AccessLevel, ...]=tuple()) -> RSSData | None:
        """当源存在且有权限返回源"""
        for i in filter(lambda x : x not in except_access, range(access, AccessLevel.NONE, -1)):
            if rss_data := self._cached_sources[i].get(source_name):
                return rss_data

    def set_rss(self, source_name: str, rss: bytes, rss_json: dict, access: AccessLevel):
        """将RSS源名称和RSS内容映射，如果是单例，还将类名和RSS内容映射"""
        if '/' in source_name: # todo 统一约束源名称
            raise RuntimeError("source_name can not contain '/'")
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
                rss_data = RSSData(file_content, {"detail": "RSS json is missed in cache"})
                file_dict[file_path.stem] = rss_data
        return file_dict


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
