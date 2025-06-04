from typing import NamedTuple

from src.website_scraper.examples.bentoml import BentoMLBlog


class CaseParam4Meta(NamedTuple):
    cls_instance: type
    expect_source_info: dict[str, str]
    table_name: str


source_info_of_BentoMLBlog = {
        'key4sort': 'pub_time',
        'link': 'https://www.bentoml.com/blog',
        'name': 'BentoML Blog'
}


scrapers_params = [
    CaseParam4Meta(BentoMLBlog, source_info_of_BentoMLBlog, "BentoML Blog"),
]
