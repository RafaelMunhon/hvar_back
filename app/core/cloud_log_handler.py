import logging
from google.cloud import logging as cloud_logging
from google.cloud.logging.handlers import CloudLoggingHandler
from google.cloud.logging import Resource
from google.cloud.logging import Client
import os

def setup_cloud_logging(logger_name: str = None) -> logging.Logger:
    """Configure logging to use Google Cloud Logging"""
    try:
        # Get the logger
        logger = logging.getLogger(logger_name or __name__)
        
        # Create a Cloud Logging client
        client = Client()
        
        # Create a handler
        handler = CloudLoggingHandler(client)
        
        # Set the log level
        handler.setLevel(logging.INFO)
        
        # Create a formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        # Add the handler to the logger
        logger.addHandler(handler)
        
        # Set the log level
        logger.setLevel(logging.INFO)
        
        logger.info("Cloud Logging configured successfully")
        return logger
        
    except Exception as e:
        print(f"Error setting up Cloud Logging: {str(e)}")
        # Fallback to basic logging
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(logger_name or __name__) 