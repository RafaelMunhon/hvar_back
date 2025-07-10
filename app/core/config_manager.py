"""Configuration management system.

This module provides a centralized configuration management system that handles:
- Environment-based configuration
- Configuration validation
- Dynamic configuration updates
- Configuration caching
- Secure storage of sensitive values
"""

import os
import json
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class BaseConfig:
    """Base configuration class with common validation methods"""
    
    def validate(self) -> bool:
        """Validate configuration values"""
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

@dataclass
class ResourceConfig(BaseConfig):
    """Resource management configuration"""
    temp_file_max_age: int = 3600  # Maximum age of temporary files in seconds
    temp_file_cleanup_interval: int = 300  # Cleanup interval in seconds
    max_temp_files: int = 1000  # Maximum number of temporary files
    temp_file_base_path: str = field(default_factory=lambda: str(Path("app/arquivosTemporarios")))
    
    # HTTP Session configuration
    max_connections: int = 100
    max_keepalive_connections: int = 30
    keepalive_timeout: int = 30
    
    # Memory management
    memory_high_water_mark: float = 0.8  # 80% memory usage triggers cleanup
    memory_low_water_mark: float = 0.6  # Clean until we reach 60% usage
    memory_check_interval: int = 60  # Check memory every 60 seconds

@dataclass
class APIConfig(BaseConfig):
    """API-related configuration"""
    project_id: str = os.getenv('GCP_PROJECT_ID', 'conteudo-autenticare')
    bucket_name: str = os.getenv('BUCKET_NAME', 'conteudo-autenticare-audios')
    pexels_api_key: str = os.getenv('PEXELS_API_KEY', 'Yuyg91HW4pxA7DPLVrJiacMnmiBcNvHgp0rT8hs00SEyJmRSANHUeuwB')
    jamendo_client_id: str = os.getenv('JAMENDO_CLIENT_ID', '1b32d833')
    envato_api_token: str = os.getenv('ENVATO_API_TOKEN', '7BGGwCRsTuQCucq2Vq3yfqJodv3Rer4H')
    heygen_api_key: str = os.getenv('HEYGEN_API_KEY', 'ZDg3ZjdhZWY5YWNlNDRmOWI1OTI3NDkyODM4NWMzNzUtMTczMzg2Mjc0Ng==')
    google_credentials: str = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'conteudo-autenticare-d2aaae9aeffe.json')
    
    def validate(self) -> bool:
        """Validate API configuration"""
        if not self.project_id:
            logger.error("GCP Project ID not configured")
            return False
        if not self.bucket_name:
            logger.error("Bucket name not configured")
            return False
        return True

@dataclass
class SecurityConfig(BaseConfig):
    """Security-related configuration"""
    ssl_verify: bool = True
    ssl_cert_path: Optional[str] = None
    min_tls_version: str = "TLSv1_2"
    verify_hostname: bool = True
    
    def validate(self) -> bool:
        """Validate security configuration"""
        if self.ssl_cert_path and not os.path.exists(self.ssl_cert_path):
            logger.error(f"SSL certificate not found at {self.ssl_cert_path}")
            return False
        return True

class ConfigManager:
    """Centralized configuration management system"""
    
    _instance = None
    _config_cache = {}
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._load_environment()
            self._initialized = True
    
    def _load_environment(self):
        """Load environment variables"""
        # Clear all LRU caches first
        self.get_resource_config.cache_clear()
        self.get_api_config.cache_clear()
        self.get_security_config.cache_clear()
        
        env_file = os.getenv('ENV_FILE', '.env')
        logger.info(f"Attempting to load environment from: {env_file}")
        
        if os.path.exists(env_file):
            logger.info(f"Environment file exists at: {os.path.abspath(env_file)}")
            # Force reload of environment variables
            load_dotenv(env_file, override=True)
            logger.info(f"Loaded environment from {env_file}")
            
            # Debug: Print all environment variables (masked)
            for key in ['HEYGEN_API_KEY', 'GCP_PROJECT_ID', 'BUCKET_NAME', 'PEXELS_API_KEY']:
                value = os.getenv(key)
                if value:
                    masked = f"{value[:5]}...{value[-5:]}" if len(value) > 10 else "***"
                    logger.info(f"Environment variable loaded - {key}: {masked}")
                else:
                    logger.warning(f"Environment variable not found: {key}")
            
            # Only set initialized if we have the required variables
            required_vars = ['HEYGEN_API_KEY', 'GCP_PROJECT_ID']
            if all(os.getenv(var) for var in required_vars):
                self._initialized = True
                logger.info("Environment initialization complete")
            else:
                self._initialized = False
                logger.warning("Missing required environment variables")
        else:
            logger.warning(f"Environment file not found: {env_file}")
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"Absolute path attempted: {os.path.abspath(env_file)}")
            self._initialized = False
    
    @lru_cache()
    def get_resource_config(self) -> ResourceConfig:
        """Get resource management configuration"""
        if not self._initialized:
            self._load_environment()
        return ResourceConfig()
    
    @lru_cache()
    def get_api_config(self) -> APIConfig:
        """Get API configuration"""
        if not self._initialized:
            self._load_environment()
        config = APIConfig()
        if not config.heygen_api_key:
            logger.warning("HeyGen API Key is empty in APIConfig")
            self._initialized = False
        return config
    
    @lru_cache()
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration"""
        if not self._initialized:
            self._load_environment()
        return SecurityConfig()
    
    def reload_config(self):
        """Reload all configurations"""
        # Clear all LRU caches
        self.get_resource_config.cache_clear()
        self.get_api_config.cache_clear()
        self.get_security_config.cache_clear()
        
        # Reset initialization flag
        self._initialized = False
        
        # Reload environment
        self._load_environment()
        logger.info("Configuration reloaded")
    
    def validate_all(self) -> bool:
        """Validate all configurations"""
        configs = [
            self.get_resource_config(),
            self.get_api_config(),
            self.get_security_config()
        ]
        return all(config.validate() for config in configs)

# Global instance
_config_manager = None

def get_config_manager() -> ConfigManager:
    """Get the global ConfigManager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager 