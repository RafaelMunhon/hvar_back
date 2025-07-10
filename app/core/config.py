import os
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import timedelta

from app.config.ffmpeg import get_temp_files_path

@dataclass
class ResourceConfig:
    """Resource management configuration"""
    
    # Temporary file management
    temp_file_lifetime: timedelta = timedelta(hours=1)
    temp_cleanup_interval: timedelta = timedelta(minutes=30)
    temp_dir: str = get_temp_files_path()
    
    # HTTP session management
    max_connections: int = 100
    max_connections_per_host: int = 20
    keepalive_timeout: int = 120
    enable_cleanup_closed: bool = True
    force_close: bool = False
    
    # Memory management
    max_memory_mb: int = 1024  # Maximum memory usage in MB
    memory_check_interval: timedelta = timedelta(minutes=5)
    
    # Cache management
    cache_size: int = 128  # LRU cache size
    cache_ttl: timedelta = timedelta(hours=1)
    
    @classmethod
    def get_default(cls) -> 'ResourceConfig':
        """Get default resource configuration"""
        return cls()
    
    def get_temp_dir(self) -> str:
        """Get temporary directory path, creating if it doesn't exist"""
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)
        return self.temp_dir
    
    def get_http_config(self) -> Dict:
        """Get HTTP client configuration"""
        return {
            'max_connections': self.max_connections,
            'max_connections_per_host': self.max_connections_per_host,
            'keepalive_timeout': self.keepalive_timeout,
            'enable_cleanup_closed': self.enable_cleanup_closed,
            'force_close': self.force_close
        }
    
    def get_memory_limit_bytes(self) -> int:
        """Get memory limit in bytes"""
        return self.max_memory_mb * 1024 * 1024 