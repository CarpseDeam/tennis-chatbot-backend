# api/dependencies.py
"""
This module defines reusable dependencies for the API, such as security checks.
"""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

from config import settings

# This tells FastAPI to look for a header named 'X-Admin-API-Key'
api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)

async def verify_admin_key(key: str = Security(api_key_header)):
    """
    Verifies that the provided API key in the header matches the one in settings.
    This protects an endpoint from public access.
    """
    if not key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An admin API key is required."
        )
    if key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin API key."
        )