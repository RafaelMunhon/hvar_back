"""Resource management system.

This module provides centralized resource management for:
- Temporary files
- HTTP sessions
- Memory usage monitoring
"""

import os
import logging
import tempfile
import asyncio
import aiohttp
import psutil
from typing import Optional, Dict, Set
from datetime import datetime, timedelta
from functools import wraps
from contextlib import asynccontextmanager
import time
import ssl

from app.core.config_manager import get_config_manager

logger = logging.getLogger(__name__)

class ResourceManager:
    """Centralized resource management"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ResourceManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize resource manager"""
        if not self._initialized:
            self._temp_files: Set[str] = set()
            self._http_sessions: Dict[str, aiohttp.ClientSession] = {}
            self._cleanup_task = None
            self._initialized = False
    
    async def initialize(self):
        """Initialize the resource manager"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:  # Double check
                return
                
            # Get configuration
            config = get_config_manager()
            resource_config = config.get_resource_config()
            
            # Create temp directory if it doesn't exist
            os.makedirs(resource_config.temp_file_base_path, exist_ok=True)
            
            # Start cleanup loop
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._initialized = True
            logger.info("✓ ResourceManager initialized successfully")
    
    async def _cleanup_loop(self):
        """Background task to clean up resources"""
        config = get_config_manager().get_resource_config()
        
        while True:
            try:
                # Clean up temporary files
                await self.cleanup()
                
                # Check memory usage
                memory = psutil.virtual_memory()
                if memory.percent >= config.memory_high_water_mark * 100:
                    logger.warning(f"High memory usage detected: {memory.percent}%")
                    # Trigger garbage collection and extra cleanup
                    import gc
                    gc.collect()
                    
                # Wait for next cleanup interval
                await asyncio.sleep(config.temp_file_cleanup_interval)
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(60)  # Wait a bit longer on error
    
    async def cleanup(self):
        """Clean up resources"""
        config = get_config_manager().get_resource_config()
        
        # Clean up temporary files
        current_time = time.time()
        files_to_remove = []
        
        for temp_file in self._temp_files:
            try:
                if not os.path.exists(temp_file):
                    files_to_remove.append(temp_file)
                    continue
                    
                # Check file age
                stats = os.stat(temp_file)
                age = current_time - stats.st_mtime
                
                if age > config.temp_file_max_age:
                    os.remove(temp_file)
                    files_to_remove.append(temp_file)
                    
            except Exception as e:
                logger.error(f"Error cleaning up temp file {temp_file}: {e}")
                files_to_remove.append(temp_file)
        
        # Update tracking set
        self._temp_files.difference_update(files_to_remove)
        
        # Clean up old HTTP sessions
        sessions_to_remove = []
        for session_id, session in self._http_sessions.items():
            try:
                if session.closed:
                    sessions_to_remove.append(session_id)
            except Exception as e:
                logger.error(f"Error checking HTTP session {session_id}: {e}")
                sessions_to_remove.append(session_id)
        
        # Close and remove old sessions
        for session_id in sessions_to_remove:
            try:
                if session_id in self._http_sessions:
                    await self._http_sessions[session_id].close()
                    del self._http_sessions[session_id]
            except Exception as e:
                logger.error(f"Error closing HTTP session {session_id}: {e}")
    
    @asynccontextmanager
    async def temp_file(self, suffix: Optional[str] = None, delete: bool = True) -> str:
        """Create and manage a temporary file
        
        Args:
            suffix: Optional file suffix/extension
            delete: Whether to delete the file when context exits (default: True)
        
        Returns:
            str: Path to temporary file
        """
        config = get_config_manager().get_resource_config()
        
        # Check if we're at the limit
        if len(self._temp_files) >= config.max_temp_files:
            await self.cleanup()  # Try to clean up first
            if len(self._temp_files) >= config.max_temp_files:
                raise RuntimeError("Maximum number of temporary files reached")
        
        # Create temp file in configured directory
        temp_path = os.path.join(
            config.temp_file_base_path,
            next(tempfile._get_candidate_names()) + (suffix or '')
        )
        
        self._temp_files.add(temp_path)
        try:
            yield temp_path
        finally:
            try:
                if delete and os.path.exists(temp_path):
                    os.remove(temp_path)
                if delete:  # Only remove from tracking if we're deleting
                    self._temp_files.remove(temp_path)
            except Exception as e:
                logger.error(f"Error removing temporary file {temp_path}: {e}")
    
    @asynccontextmanager
    async def http_session(self, session_id: str = "default") -> aiohttp.ClientSession:
        """Get or create an HTTP session"""
        if session_id not in self._http_sessions:
            config = get_config_manager()
            resource_config = config.get_resource_config()
            security_config = config.get_security_config()
            
            from app.utils.ssl_config import SSLConfig, SSLContextBuilder
            
            # Setup SSL
            ssl_config = SSLConfig(
                verify_ssl=security_config.ssl_verify,
                minimum_version=ssl.TLSVersion[security_config.min_tls_version],
                verify_hostname=security_config.verify_hostname,
                cert_path=security_config.ssl_cert_path
            )
            ssl_builder = SSLContextBuilder(ssl_config)
            
            # Create session with configured limits
            connector = aiohttp.TCPConnector(
                ssl=ssl_builder.create_context(),
                limit=resource_config.max_connections,
                limit_per_host=resource_config.max_keepalive_connections,
                enable_cleanup_closed=True
            )
            
            self._http_sessions[session_id] = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    total=resource_config.keepalive_timeout
                )
            )
        
        try:
            yield self._http_sessions[session_id]
        except Exception as e:
            logger.error(f"Error with HTTP session {session_id}: {e}")
            # Close and remove session on error
            if session_id in self._http_sessions:
                await self._http_sessions[session_id].close()
                del self._http_sessions[session_id]
            raise
    
    async def close(self):
        """Close all resources"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all HTTP sessions
        for session in self._http_sessions.values():
            await session.close()
        self._http_sessions.clear()
        
        # Clean up all temp files
        await self.cleanup()
        self._initialized = False
        logger.info("✓ ResourceManager shutdown successful")

def get_resource_manager() -> ResourceManager:
    """Get the global ResourceManager instance"""
    return ResourceManager()

def with_resources(func):
    """Decorator to ensure ResourceManager is initialized"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        manager = get_resource_manager()
        await manager.initialize()
        return await func(*args, **kwargs)
    return wrapper 