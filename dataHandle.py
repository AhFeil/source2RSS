import os
from pathlib import Path
import logging
import json
from dataclasses import dataclass

from configHandle import config
from src.website_scraper import AccessLevel


@dataclass
class RSSData:
    xml: str
    json: dict


class RSSCache:
    """内存里缓存的RSS数据"""
    def __init__(self, rss_dir: str, rss_admin_dir: str) -> None:
        self.rss_dir, self.rss_admin_dir = Path(rss_dir), Path(rss_admin_dir)
        self._public: dict[str, RSSData] = RSSCache._load_files_to_dict(self.rss_dir)
        self._admin: dict[str, RSSData] = RSSCache._load_files_to_dict(self.rss_admin_dir)

    def get_rss_or_None(self, source_name: str) -> RSSData | None:
        return self._public.get(source_name)

    def get_admin_rss_or_None(self, source_name: str) -> RSSData | None:
        return self._admin.get(source_name)

    def get_rss_list(self) -> list[str]:
        return sorted([rss for rss in self._public])

    def get_admin_rss_list(self) -> list[str]:
        return sorted([rss for rss in self._admin])

    def set_rss(self, source_name: str, rss: bytes, rss_json: dict, cls_id_or_none: str | None, access: AccessLevel):
        """将RSS源名称和RSS内容映射，如果是单例，还将类名和RSS内容映射"""
        rss_data = RSSData(rss.decode(), rss_json)
        if access == AccessLevel.ADMIN:
            self._admin[source_name] = rss_data
            if cls_id_or_none:
                self._admin[cls_id_or_none] = rss_data
        else:
            self._public[source_name] = rss_data
            if cls_id_or_none:
                self._public[cls_id_or_none] = rss_data
        rss_filepath = self.rss_dir / (source_name + ".xml")
        with open(rss_filepath, 'wb') as rss_file:   # todo 退出时保存一次
            rss_file.write(rss)

    def rss_is_absent(self, source_name: str) -> bool:
        return not (source_name in self._public or source_name in self._admin)

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
        self.rss_cache = RSSCache(config.rss_dir, config.rss_admin_dir)

        # 从文件里加载用户数据
        self._users = {"invite_code": None, "left_count": 0, "users": []}
        if not os.path.exists(config.users_file):
            with open(config.users_file, 'w', encoding="utf-8") as f:
                json.dump(self._users, f)
        else:
            with open(config.users_file, 'r', encoding="utf-8") as f:
                self._users = json.load(f)

        # DB
        from src.data import DatabaseIntf
        if config.mongodb_uri is not None:
            from src.data import MongodbIntf, MongodbConnInfo
            info = MongodbConnInfo(config.mongodb_uri, config.mongo_dbname, config.source_meta)
            self.db_intf: DatabaseIntf = MongodbIntf.connect(info)
        else:
            from src.data import SQliteIntf, SQliteConnInfo
            info = SQliteConnInfo(config.sqlite_uri)
            self.db_intf: DatabaseIntf = SQliteIntf.connect(info)

    def get_users_and_etc(self) -> dict:
        return self._users

    def save_users_and_etc(self, code, count, users: list):
        self._users["invite_code"] = code
        self._users["left_count"] = count
        self._users["users"] = users
        with open(config.users_file, 'w', encoding="utf-8") as f:
            json.dump(self._users, f)


data = Data(config)
