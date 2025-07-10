from flask import Blueprint, jsonify
from app.core.metrics import get_metrics_collector
from app.core.middleware import request_logger

metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route('/metrics', methods=['GET'])
@request_logger()
def get_metrics():
    """Get current application metrics"""
    metrics = get_metrics_collector()
    return jsonify(metrics.get_metrics())

@metrics_bp.route('/metrics/health', methods=['GET'])
@request_logger()
def health_check():
    """Health check endpoint"""
    metrics = get_metrics_collector()
    data = metrics.get_metrics()
    
    # Calculate error rate
    total_requests = data['requests']
    total_errors = data['errors']
    error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
    
    # Calculate average latency
    latencies = data['latency']
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    
    health_status = {
        'status': 'healthy' if error_rate < 5 and avg_latency < 1 else 'degraded',
        'error_rate': f"{error_rate:.2f}%",
        'average_latency': f"{avg_latency:.2f}s",
        'total_requests': total_requests,
        'total_errors': total_errors,
        'uptime': data['start_time']
    }
    
    return jsonify(health_status) 