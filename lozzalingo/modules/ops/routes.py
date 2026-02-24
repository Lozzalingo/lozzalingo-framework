"""
Ops Routes
==========

Public health endpoint and admin ops dashboard.
"""

import json
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import current_app, jsonify, render_template, request, redirect, session, url_for

from . import ops_health_bp, ops_admin_bp


# ---------------------------------------------------------------------------
# Auth decorator (same pattern as settings/routes.py)
# ---------------------------------------------------------------------------

def admin_required(f):
    """Decorator to require admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _get_disk_usage():
    """Get disk usage for root partition."""
    try:
        usage = shutil.disk_usage('/')
        return {
            'total_gb': round(usage.total / (1024 ** 3), 1),
            'used_gb': round(usage.used / (1024 ** 3), 1),
            'free_gb': round(usage.free / (1024 ** 3), 1),
            'percent': round((usage.used / usage.total) * 100, 1),
        }
    except Exception as e:
        return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0, 'error': str(e)}


def _get_memory_info():
    """Get memory info from /proc/meminfo (Linux) with macOS fallback."""
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()

        mem = {}
        for line in lines:
            parts = line.split()
            key = parts[0].rstrip(':')
            value_kb = int(parts[1])
            mem[key] = value_kb

        total_kb = mem.get('MemTotal', 0)
        available_kb = mem.get('MemAvailable', mem.get('MemFree', 0))
        swap_total_kb = mem.get('SwapTotal', 0)
        swap_free_kb = mem.get('SwapFree', 0)

        used_kb = total_kb - available_kb
        swap_used_kb = swap_total_kb - swap_free_kb

        return {
            'total_mb': round(total_kb / 1024, 1),
            'used_mb': round(used_kb / 1024, 1),
            'available_mb': round(available_kb / 1024, 1),
            'percent': round((used_kb / total_kb) * 100, 1) if total_kb else 0,
            'swap_total_mb': round(swap_total_kb / 1024, 1),
            'swap_used_mb': round(swap_used_kb / 1024, 1),
            'swap_enabled': swap_total_kb > 0,
        }
    except FileNotFoundError:
        # macOS fallback — limited info via os.sysconf
        try:
            import resource
            page_size = os.sysconf('SC_PAGE_SIZE')
            total_pages = os.sysconf('SC_PHYS_PAGES')
            total_mb = round((page_size * total_pages) / (1024 ** 2), 1)
            return {
                'total_mb': total_mb,
                'used_mb': 0,
                'available_mb': total_mb,
                'percent': 0,
                'swap_total_mb': 0,
                'swap_used_mb': 0,
                'swap_enabled': True,  # macOS always has swap
                'note': 'Limited info on macOS',
            }
        except Exception:
            return {
                'total_mb': 0, 'used_mb': 0, 'available_mb': 0, 'percent': 0,
                'swap_total_mb': 0, 'swap_used_mb': 0, 'swap_enabled': True,
                'note': 'Could not read memory info',
            }
    except Exception as e:
        return {
            'total_mb': 0, 'used_mb': 0, 'available_mb': 0, 'percent': 0,
            'swap_total_mb': 0, 'swap_used_mb': 0, 'swap_enabled': False,
            'error': str(e),
        }


def _get_uptime():
    """Get server uptime from /proc/uptime (Linux) with fallback."""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])

        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)

        return {
            'seconds': round(uptime_seconds),
            'formatted': f'{days}d {hours}h {minutes}m',
            'days': days,
        }
    except FileNotFoundError:
        # macOS fallback via sysctl
        try:
            result = subprocess.run(
                ['sysctl', '-n', 'kern.boottime'],
                capture_output=True, text=True, timeout=5
            )
            # Parse: { sec = 1234567890, usec = 0 } ...
            import re
            match = re.search(r'sec\s*=\s*(\d+)', result.stdout)
            if match:
                boot_time = int(match.group(1))
                uptime_seconds = time.time() - boot_time
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                return {
                    'seconds': round(uptime_seconds),
                    'formatted': f'{days}d {hours}h {minutes}m',
                    'days': days,
                }
        except Exception:
            pass
        return {'seconds': 0, 'formatted': 'unknown', 'days': 0}
    except Exception:
        return {'seconds': 0, 'formatted': 'unknown', 'days': 0}


def _get_load_average():
    """Get system load average."""
    try:
        load1, load5, load15 = os.getloadavg()
        return {
            '1min': round(load1, 2),
            '5min': round(load5, 2),
            '15min': round(load15, 2),
        }
    except (OSError, AttributeError):
        return {'1min': 0, '5min': 0, '15min': 0}


def _compute_status(disk, memory):
    """Compute overall status and issues list from disk/memory metrics."""
    issues = []
    status = 'ok'

    # Disk checks
    disk_pct = disk.get('percent', 0)
    if disk_pct >= 90:
        issues.append({'type': 'disk_critical', 'message': f'Disk usage critical: {disk_pct}%'})
        status = 'critical'
    elif disk_pct >= 80:
        issues.append({'type': 'disk_warning', 'message': f'Disk usage high: {disk_pct}%'})
        if status != 'critical':
            status = 'warning'

    # Memory checks
    mem_pct = memory.get('percent', 0)
    if mem_pct >= 95:
        issues.append({'type': 'memory_critical', 'message': f'Memory usage critical: {mem_pct}%'})
        status = 'critical'
    elif mem_pct >= 85:
        issues.append({'type': 'memory_warning', 'message': f'Memory usage high: {mem_pct}%'})
        if status != 'critical':
            status = 'warning'

    # Swap check
    if not memory.get('swap_enabled', True):
        issues.append({'type': 'no_swap', 'message': 'No swap space configured'})
        if status != 'critical':
            status = 'warning'

    return status, issues


def _get_recent_errors(limit=50):
    """Query app_logs for ERROR/CRITICAL entries in last 24h."""
    try:
        from lozzalingo.core.database import Database
        from lozzalingo.core.config import Config

        db_path = current_app.config.get('ANALYTICS_DB', None)
        if not db_path and hasattr(Config, 'ANALYTICS_DB'):
            db_path = Config.ANALYTICS_DB
        if not db_path:
            db_path = os.getenv('ANALYTICS_DB', '')

        if not db_path or not os.path.exists(db_path):
            return []

        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()

        with Database.connect(db_path) as conn:
            conn.row_factory = _dict_factory
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, timestamp, level, source, message, details, request_path
                FROM app_logs
                WHERE level IN ('ERROR', 'CRITICAL')
                AND timestamp > ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (cutoff, limit))
            return cursor.fetchall()
    except Exception as e:
        current_app.logger.debug(f"ops: Could not query recent errors: {e}")
        return []


def _get_error_count_last_hour():
    """Count 5xx / ERROR entries in last hour for error-spike detection."""
    try:
        from lozzalingo.core.database import Database
        from lozzalingo.core.config import Config

        db_path = current_app.config.get('ANALYTICS_DB', None)
        if not db_path and hasattr(Config, 'ANALYTICS_DB'):
            db_path = Config.ANALYTICS_DB
        if not db_path:
            db_path = os.getenv('ANALYTICS_DB', '')

        if not db_path or not os.path.exists(db_path):
            return 0

        cutoff = (datetime.now() - timedelta(hours=1)).isoformat()

        with Database.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM app_logs
                WHERE level IN ('ERROR', 'CRITICAL')
                AND timestamp > ?
            """, (cutoff,))
            return cursor.fetchone()[0]
    except Exception:
        return 0


def _dict_factory(cursor, row):
    """sqlite3 row factory that returns dicts."""
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


def _auto_docker_cleanup():
    """Run docker system prune automatically. Rate-limited to once per 6 hours via app_logs."""
    try:
        from lozzalingo.core.database import Database
        from lozzalingo.core.config import Config

        db_path = current_app.config.get('ANALYTICS_DB', None)
        if not db_path and hasattr(Config, 'ANALYTICS_DB'):
            db_path = Config.ANALYTICS_DB
        if not db_path:
            db_path = os.getenv('ANALYTICS_DB', '')

        # Check rate limit — skip if we ran cleanup in last 6 hours
        if db_path and os.path.exists(db_path):
            cutoff = (datetime.now() - timedelta(hours=6)).isoformat()
            with Database.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM app_logs
                    WHERE source = 'ops_auto_cleanup'
                    AND timestamp > ?
                """, (cutoff,))
                if cursor.fetchone()[0] > 0:
                    return  # Already ran recently

        result = subprocess.run(
            ['docker', 'system', 'prune', '-af', '--filter', 'until=72h'],
            capture_output=True, text=True, timeout=60
        )

        from lozzalingo.core import db_log
        db_log('info', 'ops_auto_cleanup', f'Auto Docker cleanup (rc={result.returncode})', {
            'stdout': result.stdout[:500],
            'returncode': result.returncode,
        })
    except FileNotFoundError:
        pass  # Docker not available (e.g. running outside container)
    except Exception as e:
        current_app.logger.debug(f"ops: auto cleanup failed: {e}")


def _build_health_response(include_errors=False):
    """Build the full health check response dict."""
    disk = _get_disk_usage()
    memory = _get_memory_info()
    uptime = _get_uptime()
    load = _get_load_average()
    status, issues = _compute_status(disk, memory)

    result = {
        'status': status,
        'timestamp': datetime.now().isoformat(),
        'checks': {
            'disk': disk,
            'memory': memory,
            'uptime': uptime,
        },
        'issues': issues,
    }

    if include_errors:
        result['load'] = load
        result['platform'] = {
            'system': platform.system(),
            'release': platform.release(),
            'python': platform.python_version(),
        }
        result['error_count_1h'] = _get_error_count_last_hour()

    return result, status


# ---------------------------------------------------------------------------
# Public routes (ops_health_bp — no auth)
# ---------------------------------------------------------------------------

@ops_health_bp.route('/')
@ops_health_bp.route('')
def health_check():
    """Public health endpoint for uptime monitors."""
    data, status = _build_health_response()
    code = 503 if status == 'critical' else 200
    return jsonify(data), code


# ---------------------------------------------------------------------------
# Admin routes (ops_admin_bp — session auth)
# ---------------------------------------------------------------------------

@ops_admin_bp.route('/')
@admin_required
def ops_dashboard():
    """Admin ops dashboard page."""
    data, status = _build_health_response(include_errors=True)
    errors = _get_recent_errors(limit=50)
    return render_template('ops/ops_dashboard.html', health=data, status=status, errors=errors)


@ops_admin_bp.route('/api/health')
@admin_required
def api_health_detail():
    """Detailed health JSON for dashboard auto-refresh."""
    data, _ = _build_health_response(include_errors=True)
    data['recent_errors'] = _get_recent_errors(limit=20)
    return jsonify(data)


@ops_admin_bp.route('/api/errors')
@admin_required
def api_errors():
    """Recent errors from app_logs for the error feed."""
    limit = request.args.get('limit', 50, type=int)
    errors = _get_recent_errors(limit=min(limit, 200))
    return jsonify({'errors': errors, 'count': len(errors)})


@ops_admin_bp.route('/api/docker-cleanup', methods=['POST'])
@admin_required
def api_docker_cleanup():
    """Trigger docker system prune from admin UI."""
    try:
        result = subprocess.run(
            ['docker', 'system', 'prune', '-af', '--filter', 'until=72h'],
            capture_output=True, text=True, timeout=60
        )
        from lozzalingo.core import db_log
        db_log('info', 'ops', 'Docker cleanup triggered from admin UI', {
            'stdout': result.stdout[:500],
            'stderr': result.stderr[:500],
            'returncode': result.returncode,
        })
        return jsonify({
            'success': True,
            'output': result.stdout[:1000],
            'returncode': result.returncode,
        })
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'Docker not found on this system'}), 404
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Docker cleanup timed out'}), 504
    except Exception as e:
        from lozzalingo.core import db_log
        db_log('error', 'ops', 'Docker cleanup failed', {'error': str(e)})
        return jsonify({'success': False, 'error': str(e)}), 500
