import sys
import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional
import traceback
from logging.handlers import RotatingFileHandler
import os
from app.core.cloud_log_handler import setup_cloud_logging

class JsonFormatter(logging.Formatter):
    """Formatter that outputs JSON strings after gathering all available info"""
    def format(self, record):
        """Formats LogRecord into JSON string"""
        # Get the non-formatted message
        message = record.getMessage()
        
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': message
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
            
        # Add any custom fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
            
        return json.dumps(log_data)

def setup_logger(name: str) -> logging.Logger:
    """Setup a logger with both file and cloud logging"""
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Setup file handler
    log_file = os.path.join(logs_dir, 'app.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Get logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Add file handler
    logger.addHandler(file_handler)
    
    # Disable DEBUG logs from weasyprint
    logging.getLogger('weasyprint').setLevel(logging.WARNING)
    logging.getLogger('fontTools').setLevel(logging.WARNING)
    
    # Setup cloud logging
    try:
        cloud_logger = setup_cloud_logging(name)
        # Cloud logging handler is already added in setup_cloud_logging
    except Exception as e:
        logger.warning(f"Cloud logging setup failed: {str(e)}")
    
    return logger

# Global error tracking
_error_count = 0
_last_error = None

def track_error(error: Exception) -> None:
    """Track error occurrence"""
    global _error_count, _last_error
    _error_count += 1
    _last_error = {
        'time': datetime.utcnow().isoformat(),
        'type': type(error).__name__,
        'message': str(error),
        'traceback': traceback.format_exc()
    }
    
    # Log error to Cloud Logging
    logger = logging.getLogger('error_tracker')
    logger.error(f"Error tracked: {str(error)}", exc_info=True)

def get_error_stats() -> Dict[str, Any]:
    """Get error statistics"""
    return {
        'total_errors': _error_count,
        'last_error': _last_error
    }