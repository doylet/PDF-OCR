from fastapi import Request, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

import app.config as config

logger = logging.getLogger(__name__)
settings = config.get_settings()

security = HTTPBearer(auto_error=False)


class AuthContext:
    """User authentication context"""
    def __init__(self, user_id: Optional[str] = None, is_authenticated: bool = False):
        self.user_id = user_id
        self.is_authenticated = is_authenticated


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> AuthContext:
    """Verify API key authentication"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    
    if x_api_key != settings.api_key:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return AuthContext(user_id="api_user", is_authenticated=True)


async def optional_auth(x_api_key: Optional[str] = Header(None)) -> AuthContext:
    """Optional authentication - allows anonymous access"""
    if x_api_key and x_api_key == settings.api_key:
        return AuthContext(user_id="api_user", is_authenticated=True)
    
    return AuthContext(user_id="anonymous", is_authenticated=False)


async def verify_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = None
) -> AuthContext:
    """Verify JWT bearer token (future implementation)"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = credentials.credentials
    
    logger.warning("JWT verification not implemented - using placeholder")
    return AuthContext(user_id="jwt_user", is_authenticated=True)
