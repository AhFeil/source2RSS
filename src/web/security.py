import os
from dataclasses import dataclass
import hashlib
from typing import Self

from fastapi.security import HTTPBasic
from pydantic import BaseModel

from preproc import config, data


security = HTTPBasic()


class Identity(BaseModel):
    name: str
    passwd: str


@dataclass
class User:
    name: str
    passwd_hash: str  # 格式: salt:hexdigest
    is_administrator: bool = False

    @classmethod
    def create(cls, name: str, passwd: str) -> Self:
        """创建用户并生成加盐哈希"""
        salt = os.urandom(16)  # 生成16字节随机盐
        derived_key = User._gen_hash(passwd, salt)
        return cls(name, f"{salt.hex()}:{derived_key.hex()}", False)

    def check_passwd(self, passwd: str) -> bool:
        salt_hex, key_hex = self.passwd_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        derived_key = User._gen_hash(passwd, salt)
        return derived_key.hex() == key_hex

    @staticmethod
    def _gen_hash(passwd: str, salt):
        return hashlib.pbkdf2_hmac(
            "sha256",
            passwd.encode("utf-8"),
            salt,
            iterations=100000  # 可调整迭代次数
        )


# 非线程安全，但在单个事件循环下是协程安全的
class UserRegistry():
    _invite_code = None
    _left_count = 0
    _user_registry: dict[str, User] = {}

    @classmethod
    def get_valid_user_or_none(cls, name: str, passwd: str) -> User | None:
        """根据用户名和密码获取一个有效的实例"""
        user = cls._user_registry.get(name)
        if user is not None and user.check_passwd(passwd):
            return user
        return None

    @classmethod
    def register_user_or_none(cls, invite_code: str, name: str, passwd: str) -> User | None:
        """根据用户名和密码添加一个用户"""
        if cls._user_registry.get(name):
            return None
        if invite_code != cls._invite_code or cls._left_count <= 0:
            return None
        user = User.create(name, passwd)
        cls._user_registry[name] = user
        cls._save_users_and_etc()
        cls._left_count -= 1
        return user

    @classmethod
    def update_ic(cls, code: str, count: int, name: str, passwd: str) -> bool:
        """根据用户名和密码获取一个有效的实例"""
        if (user := cls.get_valid_user_or_none(name, passwd)) and user.is_administrator:
            cls._invite_code = code
            cls._left_count = count
            cls._save_users_and_etc()
            return True
        return False

    @classmethod
    def _load_users_and_etc(cls, users: dict) -> None:
        """加载用户到注册表里"""
        cls._invite_code = users["invite_code"]
        cls._left_count = users["left_count"]
        for (name, passwd_hash) in users["users"]:
            if name in cls._user_registry:
                raise RuntimeError
            cls._user_registry[name] = User(name, passwd_hash, False)
        user = User.create(config.query_username, config.query_password)
        user.is_administrator = True
        cls._user_registry[config.query_username] = user

    @classmethod
    def _save_users_and_etc(cls) -> None:
        """保存用户到文件里"""
        users = [(name, user.passwd_hash) for name, user in cls._user_registry.items() if name != config.query_username]
        data.save_users_and_etc(cls._invite_code, cls._left_count, users)


UserRegistry._load_users_and_etc(data.get_users_and_etc())
