from pathlib import Path
import logging

from ruamel.yaml import YAML

from src.data import DatabaseIntf, MongodbIntf, MongodbConnInfo, SQliteIntf, SQliteConnInfo


class Data:
    def __init__(self, config) -> None:
        self.config = config
        self.logger = logging.getLogger("dataHandle")
        self.yaml = YAML()

        # 内存里的RSS数据
        self._rss: dict[str, str] = Data._load_files_to_dict(config.rss_dir)

        # DB
        if config.mongodb_uri is not None:
            info = MongodbConnInfo(config.mongodb_uri, config.mongo_dbname, config.source_meta)
            self.db_intf: DatabaseIntf = MongodbIntf.connect(info)
        else:
            info = SQliteConnInfo(config.sqlite_uri)
            self.db_intf: DatabaseIntf = SQliteIntf.connect(info)

    def get_rss_or_None(self, source_file_name: str) -> str | None:
        return self._rss.get(source_file_name)

    def get_rss_list(self) -> list[str]:
        return sorted([rss for rss in self._rss if rss.endswith(".xml")])

    def set_rss(self, source_file_name: str, rss: bytes, cls_id_or_none: str | None):
        """将RSS文件名和RSS内容映射，如果是单例，还将类名和RSS内容映射"""
        rss_str = rss.decode()
        self._rss[source_file_name] = rss_str
        if cls_id_or_none:
            self._rss[cls_id_or_none] = rss_str
        rss_filepath = Path(self.config.rss_dir) / source_file_name
        with open(rss_filepath, 'wb') as rss_file:
            rss_file.write(rss)

    def rss_is_absent(self, source_file_name: str) -> bool:
        return source_file_name not in self._rss

    @staticmethod
    def _load_files_to_dict(directory):
        path = Path(directory)
        file_dict = {}
        for file_path in path.iterdir():  # 遍历目录中的条目
            if file_path.is_file():
                file_content = file_path.read_text(encoding='utf-8')
                file_dict[file_path.name] = file_content
        return file_dict
