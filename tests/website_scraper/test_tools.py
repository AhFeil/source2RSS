"""对提供的工具，如 AsyncBrowserManager 等测试"""
import pytest

from src.website_scraper.example import WebsiteScraper

@pytest.fixture()
def setup_and_tear_down():
    print("This is run before each tools test")
    yield
    print("This is run after each tools test")

def test_range_of_1(setup_and_tear_down):
    elems = [1, 3, 5, 9, 15, 36, 100]
    flag = 5
    gen = WebsiteScraper._range_of(elems, flag, lambda x, f : f > x)
    assert list(gen) == elems[1::-1]
    flag = 16
    gen = WebsiteScraper._range_of(elems, flag, lambda x, f : f > x)
    assert list(gen) == elems[4::-1]
    flag = 101
    gen = WebsiteScraper._range_of(elems, flag, lambda x, f : f > x)
    assert list(gen) == elems[::-1]

def test_range_of_2(setup_and_tear_down):
    elems = [{'v': 1}, {'v': 3}, {'v': 5}, {'v': 9}, {'v': 15}, {'v': 36}, {'v': 100}]
    flag = 5
    gen = WebsiteScraper._range_of(elems, flag, lambda x, f : f > x['v'])
    assert list(gen) == elems[1::-1]
    flag = 16
    gen = WebsiteScraper._range_of(elems, flag, lambda x, f : f > x['v'])
    assert list(gen) == elems[4::-1]
    flag = 101
    gen = WebsiteScraper._range_of(elems, flag, lambda x, f : f > x['v'])
    assert list(gen) == elems[::-1]
