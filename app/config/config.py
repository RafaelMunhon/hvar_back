"""Main configuration module.

This module provides access to all application configuration through the new
configuration management system.
"""

import os
import logging
from dotenv import load_dotenv
from app.core.config_manager import get_config_manager

logger = logging.getLogger(__name__)

def initialize_config():
    """Initialize configuration with environment variables"""
    # Initialize configuration
    logger.info("Initializing configuration manager")
    config_manager = get_config_manager()

    # Load API configuration
    logger.info("Loading API configuration")
    api_config = config_manager.get_api_config()

    # Export commonly used values
    config = {
        'PROJECT_ID': api_config.project_id,
        'BUCKET_NAME': api_config.bucket_name,
        'PEXELS_API_KEY': api_config.pexels_api_key,
        'JAMENDO_CLIENT_ID': api_config.jamendo_client_id,
        'ENVATO_API_TOKEN': api_config.envato_api_token,
        'HEYGEN_API_KEY': api_config.heygen_api_key,
    }

    # Envato API configuration
    config['ENVATO_API_URL'] = "https://api.envato.com/v1/discovery/search/search/item"
    config['ENVATO_HEADERS'] = {
        'Accept': 'application/json'
    }

    # HeyGen API configuration
    config['HEYGEN_API_URL'] = 'https://api.heygen.com/v2'
    logger.info(f"Setting up HeyGen headers with API key: {'present' if config['HEYGEN_API_KEY'] else 'missing'}")
    config['HEYGEN_HEADERS'] = {
        'Accept': 'application/json',
        'X-API-KEY': config['HEYGEN_API_KEY'],
        'Content-Type': 'application/json'
    }

    # Log configuration status
    if config_manager.validate_all():
        logger.info("✓ Configuration validated successfully")
        
        # Log masked API keys for security
        if config['HEYGEN_API_KEY']:
            masked_key = f"{config['HEYGEN_API_KEY'][:10]}...{config['HEYGEN_API_KEY'][-4:]}"
            logger.info(f"HeyGen API Key loaded: {masked_key}")
            logger.info(f"HeyGen Headers configured: {config['HEYGEN_HEADERS']}")
        else:
            logger.warning("⚠️ HeyGen API Key is empty")
    else:
        logger.warning("⚠️ Configuration validation failed")

    return config

# Initialize configuration
config = initialize_config()

# Export configuration values
PROJECT_ID = config['PROJECT_ID']
BUCKET_NAME = config['BUCKET_NAME']
PEXELS_API_KEY = config['PEXELS_API_KEY']
JAMENDO_CLIENT_ID = config['JAMENDO_CLIENT_ID']
ENVATO_API_TOKEN = config['ENVATO_API_TOKEN']
HEYGEN_API_KEY = config['HEYGEN_API_KEY']
ENVATO_API_URL = config['ENVATO_API_URL']
ENVATO_HEADERS = config['ENVATO_HEADERS']
HEYGEN_API_URL = config['HEYGEN_API_URL']
HEYGEN_HEADERS = config['HEYGEN_HEADERS'] 