"""用户注册等接口"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .security import UserRegistry

logger = logging.getLogger("users")

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


class UserCreate(BaseModel):
    invite_code: str
    name: str
    passwd: str

class InviteCodeCreate(BaseModel):
    code: str
    count: int
    name: str
    passwd: str


@router.post("/me/register", response_class=JSONResponse)
async def user_register(user_data: UserCreate):
    if user := UserRegistry.register_user_or_none(user_data.invite_code, user_data.name, user_data.passwd):
        return {"message": "User created", "user name": user.name}
    return {"message": "User failed to be created", "user name": user_data.name}

@router.post("/invite_code", response_class=JSONResponse)
async def update_invite_code(ic_data: InviteCodeCreate):
    if UserRegistry.update_ic(ic_data.code, ic_data.count, ic_data.name, ic_data.passwd):
        return {"message": "Invite Code updated"}
    return {"message": "Invite Code failed to be updated"}
