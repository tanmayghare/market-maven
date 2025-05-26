"""
Authentication and authorization for the API.
"""

import os
import secrets
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from market_maven.core.database import get_db, get_async_db
from market_maven.models.db_models import User, APIKey
from market_maven.core.logging import get_logger
from market_maven.core.cache import cache_manager, CacheKeyBuilder

logger = get_logger(__name__)

# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
bearer_scheme = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthService:
    """Authentication service for user and API key management."""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Create a JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    def generate_api_key() -> tuple[str, str]:
        """Generate a new API key and its hash."""
        # Generate a secure random API key
        api_key = f"sk_{secrets.token_urlsafe(32)}"
        
        # Hash the API key for storage
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        return api_key, api_key_hash
    
    @staticmethod
    async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
        """Authenticate a user by username and password."""
        # Check cache first
        cache_key = f"user:{username}"
        async with cache_manager.get_cache() as cache:
            cached_user = await cache.get(cache_key)
            if cached_user:
                user = User(**cached_user)
            else:
                # Query database
                result = await db.execute(
                    "SELECT * FROM users WHERE username = :username",
                    {"username": username}
                )
                user_data = result.fetchone()
                if not user_data:
                    return None
                user = User(**user_data)
                
                # Cache user data
                await cache.set(cache_key, user.dict(), ttl=300)
        
        if not AuthService.verify_password(password, user.hashed_password):
            return None
        
        return user
    
    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
        """Get a user by ID."""
        # Check cache first
        cache_key = f"user:id:{user_id}"
        async with cache_manager.get_cache() as cache:
            cached_user = await cache.get(cache_key)
            if cached_user:
                return User(**cached_user)
        
        # Query database
        result = await db.execute(
            "SELECT * FROM users WHERE id = :user_id",
            {"user_id": user_id}
        )
        user_data = result.fetchone()
        if not user_data:
            return None
        
        user = User(**user_data)
        
        # Cache user data
        async with cache_manager.get_cache() as cache:
            await cache.set(cache_key, user.dict(), ttl=300)
        
        return user
    
    @staticmethod
    async def validate_api_key(db: AsyncSession, api_key_hash: str) -> Optional[APIKey]:
        """Validate an API key hash."""
        # Check cache first
        cache_key = f"api_key:{api_key_hash}"
        async with cache_manager.get_cache() as cache:
            cached_key = await cache.get(cache_key)
            if cached_key:
                return APIKey(**cached_key)
        
        # Query database
        result = await db.execute(
            """
            SELECT ak.*, u.is_active as user_active 
            FROM api_keys ak 
            JOIN users u ON ak.user_id = u.id 
            WHERE ak.key_hash = :key_hash 
            AND ak.is_active = true 
            AND u.is_active = true
            AND (ak.expires_at IS NULL OR ak.expires_at > NOW())
            """,
            {"key_hash": api_key_hash}
        )
        key_data = result.fetchone()
        if not key_data:
            return None
        
        api_key = APIKey(**key_data)
        
        # Update usage statistics
        await db.execute(
            """
            UPDATE api_keys 
            SET last_used_at = NOW(), usage_count = usage_count + 1 
            WHERE id = :key_id
            """,
            {"key_id": api_key.id}
        )
        await db.commit()
        
        # Cache API key data
        async with cache_manager.get_cache() as cache:
            await cache.set(cache_key, api_key.dict(), ttl=300)
        
        return api_key


# Dependency functions
async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_async_db)
) -> User:
    """Get current user from JWT token."""
    token = credentials.credentials
    
    try:
        payload = AuthService.decode_token(token)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = await AuthService.get_user_by_id(db, UUID(user_id))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
        
        return user
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_from_api_key(
    api_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_async_db)
) -> Optional[User]:
    """Get current user from API key."""
    if not api_key:
        return None
    
    # Hash the API key
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Validate API key
    key_data = await AuthService.validate_api_key(db, api_key_hash)
    if not key_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    # Check rate limiting
    cache_key = f"rate_limit:{api_key_hash}"
    async with cache_manager.get_cache() as cache:
        request_count = await cache.get(cache_key, default=0)
        if request_count >= key_data.rate_limit_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        
        # Increment request count
        await cache.set(cache_key, request_count + 1, ttl=3600)
    
    # Get user
    user = await AuthService.get_user_by_id(db, key_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


async def get_current_user(
    token_user: Optional[User] = Depends(get_current_user_from_token),
    api_key_user: Optional[User] = Depends(get_current_user_from_api_key)
) -> User:
    """Get current user from either JWT token or API key."""
    user = token_user or api_key_user
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


class PermissionChecker:
    """Check user permissions for specific operations."""
    
    def __init__(self, required_scopes: List[str]):
        self.required_scopes = required_scopes
    
    async def __call__(
        self,
        user: User = Depends(get_current_active_user),
        api_key: Optional[str] = Security(api_key_header),
        db: AsyncSession = Depends(get_async_db)
    ) -> User:
        """Check if user has required permissions."""
        # If using API key, check scopes
        if api_key:
            api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            key_data = await AuthService.validate_api_key(db, api_key_hash)
            
            if key_data and key_data.scopes:
                user_scopes = set(key_data.scopes)
                required = set(self.required_scopes)
                
                if not required.issubset(user_scopes):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Missing required scopes: {required - user_scopes}"
                    )
        
        return user


# Convenience permission checkers
require_read_analysis = PermissionChecker(["read:analysis"])
require_write_trades = PermissionChecker(["write:trades"])
require_read_portfolio = PermissionChecker(["read:portfolio"])
require_admin = PermissionChecker(["admin"])


# Utility functions
def create_user_tokens(user: User) -> Dict[str, str]:
    """Create access and refresh tokens for a user."""
    access_token = AuthService.create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )
    refresh_token = AuthService.create_refresh_token(
        data={"sub": str(user.id)}
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    } 