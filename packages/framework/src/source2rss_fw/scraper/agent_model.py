import asyncio
from dataclasses import dataclass
from typing import Any

# from socketio import AsyncServer


@dataclass
class Agent:
    sid: str
    name: str
    scrapers: list[str]
    sio: Any  # AsyncServer
    pending_futures: dict[str, asyncio.Future]


@dataclass
class D_Agent:
    name: str
    scrapers: list[str]
    uri: str
