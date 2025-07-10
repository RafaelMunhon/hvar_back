import logging
from dataclasses import dataclass
from typing import Optional
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)

@dataclass
class TimeoutConfig:
    """Centralized timeout configuration"""
    
    # HTTP Client timeouts
    http_total: float = 120.0        # Total timeout for HTTP operations
    http_connect: float = 30.0       # Connection timeout
    http_sock_read: float = 30.0     # Socket read timeout
    http_sock_connect: float = 30.0  # Socket connect timeout
    
    # API specific timeouts
    api_request: float = 60.0        # Timeout for API requests
    api_response: float = 30.0       # Timeout for API response processing
    
    # Operation timeouts
    operation_total: float = 300.0   # Total timeout for complex operations
    operation_chunk: float = 60.0    # Timeout for individual operation chunks
    
    # Worker timeouts
    worker_timeout: float = 600.0    # Worker timeout (Gunicorn)
    worker_graceful: float = 300.0   # Graceful shutdown timeout
    worker_keepalive: float = 120.0  # Keep-alive timeout
    
    @classmethod
    def get_default(cls) -> 'TimeoutConfig':
        """Get default timeout configuration"""
        return cls()
    
    def get_client_timeout(self) -> ClientTimeout:
        """Get aiohttp ClientTimeout configuration"""
        return ClientTimeout(
            total=self.http_total,
            connect=self.http_connect,
            sock_read=self.http_sock_read,
            sock_connect=self.http_sock_connect
        )
    
    def get_worker_config(self) -> dict:
        """Get worker timeout configuration"""
        return {
            'timeout': self.worker_timeout,
            'graceful_timeout': self.worker_graceful,
            'keepalive': self.worker_keepalive
        }
    
    def log_config(self):
        """Log current timeout configuration"""
        logger.info("Timeout Configuration:")
        logger.info(f"- HTTP Total: {self.http_total}s")
        logger.info(f"- HTTP Connect: {self.http_connect}s")
        logger.info(f"- HTTP Socket Read: {self.http_sock_read}s")
        logger.info(f"- HTTP Socket Connect: {self.http_sock_connect}s")
        logger.info(f"- API Request: {self.api_request}s")
        logger.info(f"- API Response: {self.api_response}s")
        logger.info(f"- Operation Total: {self.operation_total}s")
        logger.info(f"- Operation Chunk: {self.operation_chunk}s")
        logger.info(f"- Worker Timeout: {self.worker_timeout}s")
        logger.info(f"- Worker Graceful: {self.worker_graceful}s")
        logger.info(f"- Worker Keepalive: {self.worker_keepalive}s") 