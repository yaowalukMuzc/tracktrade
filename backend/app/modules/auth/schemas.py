from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.modules.users.schemas import DisplayName, Locale, Timezone, UserOut

PASSWORD_MIN_LENGTH = 8


def _lower(value: str) -> str:
    return value.strip().lower()


Email = Annotated[EmailStr, AfterValidator(_lower)]
NewPassword = Annotated[str, Field(min_length=PASSWORD_MIN_LENGTH, max_length=256)]


class RegisterIn(BaseModel):
    email: Email
    password: NewPassword
    display_name: DisplayName
    locale: Locale = "th"
    timezone: Timezone = "Asia/Bangkok"
    accept_terms: Literal[True] = Field(
        description="Must be true: user accepted the terms & privacy policy"
    )


class LoginIn(BaseModel):
    email: Email
    password: Annotated[str, Field(min_length=1, max_length=256)]
    remember: bool = True


class AuthOut(BaseModel):
    user: UserOut
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
