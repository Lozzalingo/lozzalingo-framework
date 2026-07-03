"""
Client Error Logging
====================

Receives browser JavaScript errors via POST /api/client-error
and stores them in the app_logs database table.

Auto-registered by the framework - no feature flag needed.
"""

from flask import Blueprint, request, jsonify

client_error_bp = Blueprint('client_error', __name__)

# Simple in-memory rate limiter (per IP, 10 errors/minute)
_ip_counts = {}
_last_reset = [0]

def _rate_limit_check(ip):
    import time
    now = time.time()
    if now - _last_reset[0] > 60:
        _ip_counts.clear()
        _last_reset[0] = now
    count = _ip_counts.get(ip, 0)
    if count >= 10:
        return False
    _ip_counts[ip] = count + 1
    return True


@client_error_bp.route('/api/client-error', methods=['POST'])
def receive_client_error():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()

    if not _rate_limit_check(ip):
        return jsonify({'error': 'Too many errors reported'}), 429

    data = request.get_json(silent=True) or {}
    message = data.get('message')

    if not message:
        return jsonify({'error': 'message is required'}), 400

    try:
        from lozzalingo.core import db_log
        db_log('error', 'client-error', str(message)[:1000], {
            'stack': str(data.get('stack', ''))[:2000] if data.get('stack') else None,
            'sourceFile': data.get('source'),
            'line': data.get('line'),
            'column': data.get('column'),
            'url': data.get('url'),
            'project': data.get('project'),
        })
        print(f"[ClientError] {data.get('project', '?')}: {str(message)[:100]}")
        return jsonify({'ok': True})
    except Exception as e:
        print(f"[ClientError] Failed to store error: {e}")
        return jsonify({'error': 'Failed to store error'}), 500
