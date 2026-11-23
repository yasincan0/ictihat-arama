"""Üyelik uç noktalarının istek/yanıt şemaları."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH


def _check_password(value: str) -> str:
    if value.strip() != value:
        raise ValueError("Şifre başında veya sonunda boşluk olamaz")
    if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("Şifre en az bir harf ve bir rakam içermelidir")
    return value


Password = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Password
    full_name: str | None = Field(default=None, max_length=200)

    _pw = field_validator("password")(_check_password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class EmailRequest(BaseModel):
    email: EmailStr


class TokenRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Password

    _pw = field_validator("new_password")(_check_password)


class MessageResponse(BaseModel):
    mesaj: str


class QuotaResponse(BaseModel):
    sinirsiz: bool
    kullanilan: int
    hak: int | None
    kalan: int | None
    donem_baslangici: datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    email_verified: bool


class MeResponse(BaseModel):
    kullanici: UserResponse
    kota: QuotaResponse
