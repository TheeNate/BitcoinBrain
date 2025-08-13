import time
import logging
from typing import Dict, Tuple
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from config import settings

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory rate limiting middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.requests: Dict[str, list] = {}  # IP -> list of request timestamps
        self.rate_limit = settings.RATE_LIMIT_REQUESTS
        self.window_seconds = settings.RATE_LIMIT_WINDOW
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers first (proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to direct client IP
        if request.client and hasattr(request.client, "host"):
            return request.client.host
        
        return "unknown"
    
    def _clean_old_requests(self, request_times: list, current_time: float) -> list:
        """Remove request timestamps outside the time window"""
        cutoff_time = current_time - self.window_seconds
        return [req_time for req_time in request_times if req_time > cutoff_time]
    
    def _is_rate_limited(self, client_ip: str) -> Tuple[bool, int]:
        """
        Check if client is rate limited
        Returns (is_limited, requests_remaining)
        """
        current_time = time.time()
        
        # Initialize or get existing request times for this IP
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        
        # Clean old requests outside the time window
        self.requests[client_ip] = self._clean_old_requests(
            self.requests[client_ip], 
            current_time
        )
        
        # Count current requests in window
        current_requests = len(self.requests[client_ip])
        
        # Check if limit exceeded
        if current_requests >= self.rate_limit:
            return True, 0
        
        # Add current request
        self.requests[client_ip].append(current_time)
        
        return False, self.rate_limit - current_requests - 1
    
    def _should_skip_rate_limiting(self, request: Request) -> bool:
        """Check if request should skip rate limiting"""
        # Skip rate limiting for health check endpoints
        skip_paths = ["/health", "/", "/docs", "/openapi.json"]
        return request.url.path in skip_paths
    
    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting"""
        try:
            # Skip rate limiting for certain paths
            if self._should_skip_rate_limiting(request):
                return await call_next(request)
            
            # Get client IP
            client_ip = self._get_client_ip(request)
            
            # Check rate limit
            is_limited, remaining = self._is_rate_limited(client_ip)
            
            if is_limited:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "detail": f"Maximum {self.rate_limit} requests per {self.window_seconds} seconds",
                        "retry_after": self.window_seconds
                    },
                    headers={
                        "Retry-After": str(self.window_seconds),
                        "X-RateLimit-Limit": str(self.rate_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + self.window_seconds)
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to successful responses
            response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.window_seconds)
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting middleware error: {e}")
            # If rate limiting fails, allow the request through
            return await call_next(request)
    
    def cleanup_old_entries(self):
        """Periodic cleanup of old entries (call this periodically if needed)"""
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds
        
        # Clean up entries for all IPs
        for client_ip in list(self.requests.keys()):
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip] 
                if req_time > cutoff_time
            ]
            
            # Remove empty entries
            if not self.requests[client_ip]:
                del self.requests[client_ip]
        
        logger.debug(f"Cleaned up rate limiting data. Active IPs: {len(self.requests)}")
