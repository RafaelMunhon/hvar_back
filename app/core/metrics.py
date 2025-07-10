import time
import functools
import logging
from typing import Any, Callable, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Collects and reports application metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            'start_time': datetime.utcnow().isoformat(),
            'requests': 0,
            'errors': 0,
            'latency': [],
            'endpoints': {},
            'memory_usage': [],
            'api_calls': {
                'heygen': {'success': 0, 'errors': 0},
                'gcp': {'success': 0, 'errors': 0},
                'pexels': {'success': 0, 'errors': 0}
            }
        }
    
    def track_request(self, endpoint: str, method: str, status: int, duration: float):
        """Track API request metrics"""
        self.metrics['requests'] += 1
        self.metrics['latency'].append(duration)
        
        if endpoint not in self.metrics['endpoints']:
            self.metrics['endpoints'][endpoint] = {
                'total': 0,
                'errors': 0,
                'avg_latency': 0
            }
        
        self.metrics['endpoints'][endpoint]['total'] += 1
        if status >= 400:
            self.metrics['endpoints'][endpoint]['errors'] += 1
            self.metrics['errors'] += 1
        
        # Update average latency
        current_avg = self.metrics['endpoints'][endpoint]['avg_latency']
        total = self.metrics['endpoints'][endpoint]['total']
        self.metrics['endpoints'][endpoint]['avg_latency'] = (
            (current_avg * (total - 1) + duration) / total
        )
        
        # Log metrics
        logger.info(f"Request metrics - Endpoint: {endpoint}, Method: {method}, "
                   f"Status: {status}, Duration: {duration:.2f}s")
    
    def track_api_call(self, service: str, success: bool):
        """Track external API calls"""
        if service in self.metrics['api_calls']:
            if success:
                self.metrics['api_calls'][service]['success'] += 1
            else:
                self.metrics['api_calls'][service]['errors'] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.metrics

# Global metrics collector
_metrics_collector = MetricsCollector()

def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    return _metrics_collector

def timing_decorator(func: Callable) -> Callable:
    """Decorator to track function execution time"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"Function {func.__name__} executed in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Function {func.__name__} failed after {duration:.2f}s: {str(e)}")
            raise
    return wrapper 