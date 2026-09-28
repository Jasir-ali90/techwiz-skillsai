import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from src.models.enums import UserType


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    user_type: UserType
    is_active: bool