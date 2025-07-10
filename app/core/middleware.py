import time
import logging
from functools import wraps
from flask import request, g
from app.core.metrics import get_metrics_collector

logger = logging.getLogger(__name__)

def request_logger():
    """Middleware to log request details"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Start timer
            start_time = time.time()
            
            # Get request details
            request_id = request.headers.get('X-Request-ID', 'N/A')
            method = request.method
            endpoint = request.endpoint
            url = request.url
            client_ip = request.remote_addr
            
            # Log request start
            logger.info(f"Request started - ID: {request_id}, Method: {method}, "
                       f"Endpoint: {endpoint}, URL: {url}, IP: {client_ip}")
            
            # Store request ID in g for later use
            g.request_id = request_id
            
            try:
                # Execute the request
                response = f(*args, **kwargs)
                
                # Calculate duration
                duration = time.time() - start_time
                
                # Track metrics
                metrics = get_metrics_collector()
                metrics.track_request(
                    endpoint=endpoint,
                    method=method,
                    status=response.status_code,
                    duration=duration
                )
                
                # Log request completion
                logger.info(f"Request completed - ID: {request_id}, "
                           f"Status: {response.status_code}, "
                           f"Duration: {duration:.2f}s")
                
                return response
                
            except Exception as e:
                # Calculate duration
                duration = time.time() - start_time
                
                # Log error
                logger.error(f"Request failed - ID: {request_id}, "
                            f"Error: {str(e)}, Duration: {duration:.2f}s",
                            exc_info=True)
                
                # Track metrics
                metrics = get_metrics_collector()
                metrics.track_request(
                    endpoint=endpoint,
                    method=method,
                    status=500,
                    duration=duration
                )
                
                raise
                
        return decorated_function
    return decorator 