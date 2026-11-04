from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool
    is_verified: bool

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    success: bool
    message: str
    email: EmailStr


class VerifyEmailResponse(BaseModel):
    success: bool
    message: str


class MyInformationResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool
    is_verified: bool

    api_key: str
    api_key_last4: str
    api_key_created_at: datetime | None = None


class RegenerateApiKeyResponse(BaseModel):
    success: bool
    message: str

    api_key: str
    api_key_last4: str
    api_key_created_at: datetime

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    success: bool
    message: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    success: bool
    message: str
