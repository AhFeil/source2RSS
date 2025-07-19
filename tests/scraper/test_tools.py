"""
对提供的工具，如 AsyncBrowserManager 等测试

SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest -s tests/scraper/test_tools.py
"""
import pytest
import pytest_asyncio

from src.scraper.scraper import WebsiteScraper
from src.scraper.tools import create_rp


@pytest.fixture()
def setup_and_tear_down():
    print("This is run before each tools test")
    yield
    print("This is run after each tools test")

def test_range_by_desc_of_1(setup_and_tear_down):
    elems = [1, 3, 5, 9, 15, 36, 100]
    flag = 5
    gen = WebsiteScraper._range_by_desc_of(elems, flag, lambda x, f : f > x)
    assert list(gen) == elems[1::-1]
    flag = 16
    gen = WebsiteScraper._range_by_desc_of(elems, flag, lambda x, f : f > x)
    assert list(gen) == elems[4::-1]
    flag = 101
    gen = WebsiteScraper._range_by_desc_of(elems, flag, lambda x, f : f > x)
    assert list(gen) == elems[::-1]

def test_range_by_desc_of_2(setup_and_tear_down):
    elems = [{'v': 1}, {'v': 3}, {'v': 5}, {'v': 9}, {'v': 15}, {'v': 36}, {'v': 100}]
    flag = 5
    gen = WebsiteScraper._range_by_desc_of(elems, flag, lambda x, f : f > x['v'])
    assert list(gen) == elems[1::-1]
    flag = 16
    gen = WebsiteScraper._range_by_desc_of(elems, flag, lambda x, f : f > x['v'])
    assert list(gen) == elems[4::-1]
    flag = 101
    gen = WebsiteScraper._range_by_desc_of(elems, flag, lambda x, f : f > x['v'])
    assert list(gen) == elems[::-1]



@pytest_asyncio.fixture()
async def async_setup_and_tear_down():
    print("This is run before each tools test")
    yield
    print("This is run after each tools test")


@pytest.mark.asyncio
async def test_create_rp(async_setup_and_tear_down):
    # https://www.robotstxt.org/orig.html
    robots_txt = """User-agent: *
Disallow: /cyberworld/map/
Disallow: /tmp/
Disallow: /foo.html

User-agent: googlebot
Allow: /foo.html
"""
    rp = await create_rp(robots_txt)
    assert not rp.can_fetch("source2RSSbot", "https://example.com/cyberworld/map/")
    assert not rp.can_fetch("source2RSSbot", "https://example.com/tmp/")
    assert not rp.can_fetch("source2RSSbot", "https://example.com/foo.html")
    assert rp.can_fetch("source2RSSbot", "https://example.com/fuzz.html")
    assert rp.can_fetch("googlebot", "https://example.com/foo.html")
