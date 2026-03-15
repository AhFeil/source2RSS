import os
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from briefconf import BriefConfig


configfile = os.getenv("SOURCE2RSS_AGENT_CONFIG_FILE", default="config_and_data_files/config.yaml")


@dataclass(frozen=True, slots=True)
class Config(BriefConfig):
    name: str
    port: int
    enabled_web_scraper: dict[str, str]

    # 用户不应该考虑的配置，开发者可以改的
    root_dir: str

    @classmethod
    def load(cls, config_path: str) -> Self:
        configs = cls._load_config(config_path)
        current_dir = Path(__file__).resolve().parent
        return cls(
            name=configs.get("name", "vfly2_agent"),
            port=configs.get("port", 8537),
            enabled_web_scraper=configs.get('enabled_web_scraper', {}),
            root_dir = str(current_dir.parent.parent)
        )

config = Config.load(os.path.abspath(configfile))
