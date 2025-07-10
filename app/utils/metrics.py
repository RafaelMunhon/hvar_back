import time
from collections import defaultdict
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
import logging

logger = logging.getLogger(__name__)

@dataclass
class MetricPoint:
    timestamp: float
    value: float
    labels: Dict[str, str]

class MetricsCollector:
    def __init__(self):
        self.metrics: Dict[str, List[MetricPoint]] = defaultdict(list)
        self._lock = asyncio.Lock()
        
    def record_sync(self, name: str, value: float, **labels):
        """Record a metric value synchronously"""
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels
        )
        self.metrics[name].append(point)
            
    async def record_async(self, name: str, value: float, **labels):
        """Record a metric value asynchronously"""
        async with self._lock:
            self.record_sync(name, value, **labels)
            
    def get_stats_sync(self, name: str, window: Optional[timedelta] = None) -> Dict:
        """Get statistics for a metric synchronously"""
        points = self.metrics[name]
        if window:
            cutoff = time.time() - window.total_seconds()
            points = [p for p in points if p.timestamp >= cutoff]
        
        if not points:
            return {
                'count': 0,
                'min': 0,
                'max': 0,
                'avg': 0,
                'sum': 0
            }
        
        values = [p.value for p in points]
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'sum': sum(values)
        }
            
    def export_metrics(self, path: str = 'metrics'):
        """Export metrics to JSON files"""
        try:
            os.makedirs(path, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for name, points in self.metrics.items():
                filename = os.path.join(path, f'{name}_{timestamp}.json')
                with open(filename, 'w') as f:
                    json.dump([{
                        'timestamp': p.timestamp,
                        'value': p.value,
                        'labels': p.labels
                    } for p in points], f, indent=2)
            logger.info(f"Metrics exported to {path}")
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")

class GlobalMetrics:
    def __init__(self):
        self.timings = defaultdict(list)
        self.collector = MetricsCollector()

    def timing(self, method_name=None):
        """Decorator to measure execution time of a function or method."""
        def decorator(func):
            from functools import wraps
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                name = method_name or func.__name__
                start = time.time()
                try:
                    return await func(*args, **kwargs)
                finally:
                    elapsed = time.time() - start
                    self.timings[name].append(elapsed)
                    await self.collector.record_async('method_duration', elapsed, method=name)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                name = method_name or func.__name__
                start = time.time()
                try:
                    return func(*args, **kwargs)
                finally:
                    elapsed = time.time() - start
                    self.timings[name].append(elapsed)
                    self.collector.record_sync('method_duration', elapsed, method=name)
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
                
        return decorator

    def print_table(self):
        """Print metrics table to console"""
        print("\n=== MÉTRICAS DE TEMPO POR MÉTODO ===")
        print(f"{'Método':<40} | {'Chamadas':<8} | {'Média (s)':<10} | {'Total (s)':<10} | {'Máx (s)':<10} | {'Min (s)':<10}")
        print("-" * 90)
        for method, times in self.timings.items():
            if times:
                print(f"{method:<40} | {len(times):<8} | {sum(times)/len(times):<10.4f} | {sum(times):<10.4f} | {max(times):<10.4f} | {min(times):<10.4f}")
        print("=" * 90)

    def export_metrics(self, path: str = 'metrics'):
        """Export all metrics to files"""
        self.collector.export_metrics(path)

# Global instance
global_metrics = GlobalMetrics()