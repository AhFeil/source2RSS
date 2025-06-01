import os
from dataclasses import dataclass
import hashlib
from typing import Self

from fastapi.security import HTTPBasic

from preprocess import config

security = HTTPBasic()


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

    @classmethod
    def get_valid_user_none(cls, name: str, passwd: str) -> Self | None:
        """根据用户名和密码获取一个有效的实例，否则抛出异常"""
        # todo 简单实现，将来更改
        if name == config.query_username and passwd == config.query_password:
            return cls(name, "", True)
        return None

    def _check_passwd(self, passwd: str) -> bool:
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
