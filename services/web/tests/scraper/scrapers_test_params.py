from typing import NamedTuple

from src.scraper.examples.bentoml import BentoMLBlog


class CaseParam4Meta(NamedTuple):
    cls_instance: type
    expect_source_info: dict[str, str]


source_info_of_BentoMLBlog = {
        'name': 'BentoML Blog',
        'link': 'https://www.bentoml.com/blog',
        'key4sort': 'pub_time',
        'table_name': 'BentoML Blog'
}


scrapers_params = [
    CaseParam4Meta(BentoMLBlog, source_info_of_BentoMLBlog),
]
