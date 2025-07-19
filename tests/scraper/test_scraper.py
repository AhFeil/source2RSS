"""
对 WebsiteScraper 的对外接口测试即可

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s tests/scraper/test_scraper.py
"""
from datetime import datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from src.scraper import LocateInfo, Sequence, WebsiteScraper
from tests.scraper.scrapers_test_params import CaseParam4Meta, scrapers_params


@pytest_asyncio.fixture(params=scrapers_params)
async def setup_and_tear_down(request) -> AsyncGenerator[tuple[WebsiteScraper, CaseParam4Meta], None]:
    tc = request.param
    ins = await tc.cls_instance.create()
    yield ins, tc
    pass

@pytest.mark.asyncio
async def test_meta_info(setup_and_tear_down):
    ins, tc = setup_and_tear_down
    for key, val in tc.expect_source_info.items():
        assert ins.source_info[key] == val
    assert ins.table_name == tc.table_name
    assert isinstance(ins.max_wait_time, int) and ins.max_wait_time > 0

@pytest.mark.asyncio
async def test_first_add(setup_and_tear_down):
    ins, _ = setup_and_tear_down
    flags: LocateInfo = {"amount": 2} # type: ignore
    async for a in ins.get(flags):
        for val in a.values():
            assert val is not None

@pytest.mark.asyncio
async def test_get_new(setup_and_tear_down):
    ins, _ = setup_and_tear_down
    flags: LocateInfo = {ins.source_info["key4sort"]: datetime(2024, 4, 1)} # type: ignore
    async for a in ins.get(flags):
        for val in a.values():
            assert val is not None
        break

@pytest.mark.asyncio
async def test_get_from_old2new(setup_and_tear_down):
    ins, _ = setup_and_tear_down
    if ins.__class__.support_old2new:
        flags: LocateInfo = {ins.source_info["key4sort"]: datetime(2024, 4, 1)} # type: ignore
        async for a in ins.get(flags, Sequence.PREFER_OLD2NEW):
            for val in a.values():
                assert val is not None
            break
