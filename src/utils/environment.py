import random
import hashlib
from typing import Dict, List, Optional, Tuple

from playwright.async_api import Cookie, Page

from configHandle import config


def get_user_agent(name4seed: str) -> str:
    """根据字符串计算索引，返回 user agent，比如用账号名，这样每次返回的是同一个，合理"""
    amount = len(config.desktop_user_agent)
    hash_object = hashlib.md5(name4seed.encode('utf-8'))
    hex_dig = hash_object.hexdigest()
    # 使用取余运算将整数映射
    index = int(hex_dig, 16) % amount
    return config.desktop_user_agent[index]


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


if __name__ == "__main__":
    ans = get_user_agent("AhFei")
    print(ans)