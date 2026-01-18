"""Auth models for BudAI SDK."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenData(BaseModel):
    """Token data from login response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    expires_in: int = Field(..., description="Token lifetime in seconds")
    token_type: str = Field(default="Bearer", description="Token type")
    refresh_expires_in: int | None = Field(None, description="Refresh token lifetime")
    id_token: str | None = Field(None, description="ID token")
    session_state: str | None = Field(None, description="Session state")
    scope: str | None = Field(None, description="Token scope")


class TokenResponse(BaseModel):
    """Response from login/refresh token endpoints."""

    object: str = Field(default="auth_token", description="Response object type")
    message: str | None = Field(None, description="Response message")
    token: TokenData = Field(..., description="Token data")
    first_login: bool = Field(default=False, description="First login flag")
    is_reset_password: bool = Field(default=False, description="Password reset required")

    @property
    def access_token(self) -> str:
        """Get access token for convenience."""
        return self.token.access_token

    @property
    def refresh_token(self) -> str:
        """Get refresh token for convenience."""
        return self.token.refresh_token

    @property
    def expires_in(self) -> int:
        """Get token expiry for convenience."""
        return self.token.expires_in


class UserInfo(BaseModel):
    """Current user information."""

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    name: str | None = Field(None, description="User display name")
    is_active: bool = Field(default=True, description="Whether user is active")
