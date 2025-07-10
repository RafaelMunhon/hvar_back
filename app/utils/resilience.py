import logging
import random
import time
from functools import wraps
from typing import Callable, TypeVar, Optional, Dict
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self._lock = asyncio.Lock()
    
    async def record_failure(self):
        async with self._lock:
            self.failures += 1
            self.last_failure_time = datetime.now()
            if self.failures >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker opened after {self.failures} failures")
    
    async def record_success(self):
        async with self._lock:
            self.failures = 0
            self.state = "CLOSED"
            self.last_failure_time = None
    
    async def can_execute(self) -> bool:
        async with self._lock:
            if self.state == "CLOSED":
                return True
            
            if self.state == "OPEN":
                if self.last_failure_time and \
                   datetime.now() - self.last_failure_time > timedelta(seconds=self.reset_timeout):
                    self.state = "HALF-OPEN"
                    logger.info("Circuit breaker entering HALF-OPEN state")
                    return True
                return False
            
            return True  # HALF-OPEN state allows execution

class RetryConfig:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2,
        jitter_factor: float = 0.1
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter_factor = jitter_factor

class APIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable

def is_retryable_error(error: Exception) -> bool:
    """Determine if an error should trigger a retry."""
    if isinstance(error, APIError):
        return error.retryable
    
    # Network related errors
    if any(err_type in str(type(error)) for err_type in [
        'ConnectionError', 'TimeoutError', 'SSLError',
        'HTTPError', 'NetworkError', 'SocketError'
    ]):
        return True
    
    # API specific errors (e.g. rate limits, server errors)
    if hasattr(error, 'status_code'):
        status_code = getattr(error, 'status_code')
        return status_code >= 500 or status_code in [429, 408]
    
    return False

def calculate_next_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay with exponential backoff and jitter."""
    exponential_delay = min(
        config.base_delay * (config.exponential_base ** attempt),
        config.max_delay
    )
    
    # Add jitter
    jitter = random.uniform(
        -config.jitter_factor * exponential_delay,
        config.jitter_factor * exponential_delay
    )
    
    return max(0, exponential_delay + jitter)

def with_retry(config: RetryConfig = RetryConfig()):
    """
    Decorator that implements retry logic with exponential backoff and jitter.
    
    Args:
        config: RetryConfig object with retry parameters
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    if attempt > 0:
                        delay = calculate_next_delay(attempt, config)
                        logger.info(f"Retry attempt {attempt}/{config.max_retries} after {delay:.2f}s delay")
                        await asyncio.sleep(delay)
                    
                    return await func(*args, **kwargs)
                
                except Exception as e:
                    last_error = e
                    
                    if not is_retryable_error(e) or attempt >= config.max_retries:
                        logger.error(f"Error executing {func.__name__}: {str(e)}")
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_retries} failed for {func.__name__}: {str(e)}"
                    )
            
            raise last_error
        
        return wrapper
    return decorator

def with_circuit_breaker(circuit_breaker: CircuitBreaker):
    """
    Decorator that implements circuit breaker pattern.
    
    Args:
        circuit_breaker: CircuitBreaker instance to use
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if not await circuit_breaker.can_execute():
                raise APIError(
                    "Circuit breaker is open - too many recent failures",
                    retryable=False
                )
            
            try:
                result = await func(*args, **kwargs)
                await circuit_breaker.record_success()
                return result
            
            except Exception as e:
                await circuit_breaker.record_failure()
                raise
        
        return wrapper
    return decorator

# Error mapping for specific API errors
ERROR_MAPPING = {
    'INVALID_ARGUMENT': {
        'message': 'The request contains invalid arguments',
        'retryable': False
    },
    'RESOURCE_EXHAUSTED': {
        'message': 'Rate limit exceeded or quota exceeded',
        'retryable': True
    },
    'UNAVAILABLE': {
        'message': 'Service temporarily unavailable',
        'retryable': True
    },
    'DEADLINE_EXCEEDED': {
        'message': 'Request deadline exceeded',
        'retryable': True
    },
    'INTERNAL': {
        'message': 'Internal server error',
        'retryable': True
    }
}

def map_api_error(error_code: str, details: str = "") -> APIError:
    """Map API error codes to specific exceptions."""
    error_info = ERROR_MAPPING.get(error_code, {
        'message': 'Unknown API error',
        'retryable': True
    })
    
    message = f"{error_info['message']}: {details}" if details else error_info['message']
    return APIError(message, retryable=error_info['retryable']) 