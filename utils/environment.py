import random
from typing import Dict, List, Optional, Tuple

from playwright.async_api import Cookie, Page

from preprocess import config


def get_user_agent() -> str:
    return random.choice(config.desktop_user_agent)


def get_mobile_user_agent() -> str:
    return random.choice(config.mobile_user_agent)

def get_init_script() -> str:
    return config.init_script_path


def convert_cookies(cookies: Optional[List[Cookie]]) -> Tuple[str, Dict]:
    if not cookies:
        return "", {}
    cookies_str = ";".join(f"{cookie.get('name')}={cookie.get('value')}" for cookie in cookies)
    cookie_dict = {cookie.get('name'): cookie.get('value') for cookie in cookies}
    return cookies_str, cookie_dict
