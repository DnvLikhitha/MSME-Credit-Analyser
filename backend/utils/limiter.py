"""
Rate Limiting Utility — slowapi integration
===========================================
Provides a global Limiter instance using client IP address.
Used to decorate endpoints with rate limits, e.g. @limiter.limit("10/minute").
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    storage_uri="memory://",
)
