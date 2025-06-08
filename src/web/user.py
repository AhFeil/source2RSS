"""用户注册等接口"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .security import UserRegistry

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=[__name__],
)


class UserCreate(BaseModel):
    invite_code: str
    name: str
    passwd: str


@router.post("/me/register", response_class=JSONResponse)
async def user_register(user_data: UserCreate):
    if user := UserRegistry.register_user_or_none(user_data.invite_code, user_data.name, user_data.passwd):
        return {"message": "User created", "user name": user.name}
    return {"message": "User failed to be created", "user name": user_data.name}
