import os
from pathlib import Path
import logging
import json


class RSSCache:
    """内存里缓存的RSS数据"""
    def __init__(self, rss_dir: str) -> None:
        self.rss_dir = Path(rss_dir)
        self._public_rss: dict[str, str] = RSSCache._load_files_to_dict(rss_dir)
        self._public_rss_json: dict[str, dict] = {}

    def get_rss_or_None(self, source_name: str) -> str | None:
        return self._public_rss.get(source_name)

    def get_rss_json_or_None(self, source_name: str) -> dict | None:
        return self._public_rss_json.get(source_name)

    def get_rss_list(self) -> list[str]:
        return sorted([rss for rss in self._public_rss])

    def set_rss(self, source_name: str, rss: bytes, rss_json: dict, cls_id_or_none: str | None):
        """将RSS源名称和RSS内容映射，如果是单例，还将类名和RSS内容映射"""
        rss_str = rss.decode()
        self._public_rss[source_name] = rss_str
        self._public_rss_json[source_name] = rss_json
        if cls_id_or_none:
            self._public_rss[cls_id_or_none] = rss_str
            self._public_rss_json[cls_id_or_none] = rss_json
        rss_filepath = self.rss_dir / (source_name + ".xml")
        with open(rss_filepath, 'wb') as rss_file:
            rss_file.write(rss)

    def rss_is_absent(self, source_name: str) -> bool:
        return source_name not in self._public_rss or source_name not in self._public_rss_json

    @staticmethod
    def _load_files_to_dict(directory):
        path = Path(directory)
        file_dict = {}
        for file_path in path.iterdir():
            if file_path.is_file():
                file_content = file_path.read_text(encoding='utf-8')
                file_dict[file_path.stem] = file_content
        return file_dict


# 非线程安全，但在单个事件循环下是协程安全的
class Data:
    def __init__(self, config) -> None:
        self.config = config
        self.logger = logging.getLogger("dataHandle")
        self.rss_cache = RSSCache(config.rss_dir)

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


from configHandle import config  # noqa
data = Data(config)
