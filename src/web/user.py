"""用户注册等接口"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, constr

from .security import UserRegistry

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=[__name__],
)


username_password_regex = r'^[a-zA-Z0-9!@#$%^&*()_+={}\[\]<>,.?/~-]+$'

class UserCreate(BaseModel):
    invite_code: str
    name: constr(pattern=username_password_regex, min_length=3, max_length=20) # type: ignore
    passwd: constr(pattern=username_password_regex, min_length=8, max_length=32) # type: ignore


@router.post("/me/register", response_class=JSONResponse)
async def user_register(user_data: UserCreate):
    if user := UserRegistry.register_user_or_none(user_data.invite_code, user_data.name, user_data.passwd):
        return {"message": "User created", "user name": user.name}
    return {"message": "User failed to be created", "user name": user_data.name}
