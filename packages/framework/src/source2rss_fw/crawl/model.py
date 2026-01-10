from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Self


@dataclass
class ScraperNameAndParams:
    name: str  # TODO 不能是列表，只能是 list[str]
    init_params: list | tuple | str  # 如果参数只有一个，则可以为 str，多个用列表按顺序容纳，没有参数则使用空列表
    amount: int
    max_rss_item: int
    interval: int

    @classmethod
    def create(
        cls,
        cls_name: str,
        init_params_es: Iterable,
        amount: int,
        max_rss_item: int,
        interval: int,
        prefer_agent: Callable,
        agents_registry: Callable,
        i_am_remote: bool = False,
    ) -> tuple[Self, ...]:
        if cls_name == "Remote":
            return ()
        scrapers = []
        for init_params in init_params_es:
            agent_name = prefer_agent(cls_name)
            # TODO
            if agent_name == "self" or i_am_remote:
                scraper = cls(cls_name, init_params, amount, max_rss_item, interval)
            else:
                agents = agents_registry(cls_name, agent_name)
                if not agents:
                    continue
                if not init_params:
                    new_params = [agents, cls_name]
                elif isinstance(init_params, tuple | list):
                    new_params = [agents, cls_name, *init_params]
                else:
                    new_params = [agents, cls_name, init_params]
                scraper = cls("Remote", new_params, amount, max_rss_item, interval)
            scrapers.append(scraper)
        return tuple(scrapers)

    def __hash__(self):
        if self.name == "Remote":
            return hash(tuple(self.init_params[1:]))
        params = self.init_params if isinstance(self.init_params, (str, int, tuple, float, bool)) else tuple(self.init_params)
        return hash((self.name, params))

    def __eq__(self, other):
        if self.name == "Remote" and other.name == "Remote":
            return self.init_params[1:] == other.init_params[1:]
        return self.name == other.name and self.init_params == other.init_params
