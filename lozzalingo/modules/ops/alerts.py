"""
Ops Alert System
================

Email notifications with rate-limiting for infrastructure issues.
Rate-limits by querying app_logs for previous alerts — no new DB tables needed.
"""

import json
import os
from datetime import datetime, timedelta

from flask import current_app


def check_and_alert(app):
    """
    Run health checks and send email alerts if thresholds are crossed.
    Rate-limited: max one alert per issue type per 6 hours.

    Called from _setup_ops_monitoring() in lozzalingo/__init__.py.
    """
    with app.app_context():
        try:
            from .routes import _get_disk_usage, _get_memory_info, _get_error_count_last_hour

            disk = _get_disk_usage()
            memory = _get_memory_info()
            error_count = _get_error_count_last_hour()

            issues = []

            # Disk checks
            disk_pct = disk.get('percent', 0)
            if disk_pct >= 90:
                issues.append(('disk_critical', f'Disk usage critical: {disk_pct}% ({disk.get("free_gb", "?")}GB free)'))
            elif disk_pct >= 80:
                issues.append(('disk_warning', f'Disk usage high: {disk_pct}% ({disk.get("free_gb", "?")}GB free)'))

            # Memory checks
            mem_pct = memory.get('percent', 0)
            if mem_pct >= 95:
                issues.append(('memory_critical', f'Memory usage critical: {mem_pct}% ({memory.get("available_mb", "?")}MB available)'))
            elif mem_pct >= 85:
                issues.append(('memory_warning', f'Memory usage high: {mem_pct}% ({memory.get("available_mb", "?")}MB available)'))

            # Swap check
            if not memory.get('swap_enabled', True):
                issues.append(('no_swap', 'No swap space configured'))

            # Error spike check
            if error_count > 10:
                issues.append(('error_spike', f'{error_count} errors in the last hour'))

            if not issues:
                return

            # Filter to only issues that haven't been alerted recently
            alertable = []
            for issue_type, message in issues:
                if not _was_recently_alerted(issue_type):
                    alertable.append((issue_type, message))

            if not alertable:
                return

            _send_alert_email(app, alertable, disk, memory, error_count)

        except Exception as e:
            app.logger.debug(f"ops alert check failed: {e}")


def _was_recently_alerted(issue_type, hours=6):
    """Check if an alert for this issue type was sent within the last N hours."""
    try:
        from lozzalingo.core.database import Database
        from lozzalingo.core.config import Config

        db_path = current_app.config.get('ANALYTICS_DB', None)
        if not db_path and hasattr(Config, 'ANALYTICS_DB'):
            db_path = Config.ANALYTICS_DB
        if not db_path:
            db_path = os.getenv('ANALYTICS_DB', '')

        if not db_path or not os.path.exists(db_path):
            return False

        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        with Database.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM app_logs
                WHERE source = 'ops_alert'
                AND timestamp > ?
                AND details LIKE ?
            """, (cutoff, f'%"{issue_type}"%'))
            count = cursor.fetchone()[0]
            return count > 0
    except Exception:
        return False


def _send_alert_email(app, issues, disk, memory, error_count):
    """Send alert email and log it to app_logs for rate-limiting."""
    try:
        from lozzalingo.modules.email.email_service import EmailService
        from lozzalingo.core import db_log

        admin_email = app.config.get('EMAIL_ADMIN_EMAIL')
        if not admin_email:
            app.logger.debug("ops: No EMAIL_ADMIN_EMAIL configured, skipping alert email")
            return

        brand_name = app.config.get('EMAIL_BRAND_NAME', 'Lozzalingo Site')

        # Determine overall severity
        has_critical = any(t.endswith('_critical') for t, _ in issues)
        severity = 'CRITICAL' if has_critical else 'WARNING'

        issue_types = [t for t, _ in issues]
        issue_summaries = [m for _, m in issues]
        subject = f'[{severity}] {brand_name} - {issue_summaries[0]}'
        if len(issue_summaries) > 1:
            subject = f'[{severity}] {brand_name} - {len(issues)} infrastructure issues'

        # Build HTML email body
        html_body = _build_alert_html(brand_name, severity, issues, disk, memory, error_count)

        # Try to send via EmailService
        email_svc = EmailService()
        try:
            email_svc.init_app(app)
            email_svc.send_email([admin_email], subject, html_body)
        except Exception as e:
            app.logger.debug(f"ops: Failed to send alert email: {e}")

        # Log each issue type for rate-limiting
        for issue_type, message in issues:
            db_log('info', 'ops_alert', f'Alert sent: {message}', {
                'issue_type': issue_type,
                'severity': severity,
                'disk_percent': disk.get('percent', 0),
                'memory_percent': memory.get('percent', 0),
            })

    except Exception as e:
        app.logger.debug(f"ops: Alert email error: {e}")


def _build_alert_html(brand_name, severity, issues, disk, memory, error_count):
    """Build HTML alert email body with inline styles."""
    border_color = '#dc3545' if severity == 'CRITICAL' else '#ffc107'
    bg_color = '#fff5f5' if severity == 'CRITICAL' else '#fffbeb'

    issues_html = ''.join(
        f'<li style="padding: 6px 0; color: #333;">{msg}</li>'
        for _, msg in issues
    )

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: {bg_color}; border-left: 4px solid {border_color}; padding: 16px 20px; margin-bottom: 20px;">
            <h2 style="margin: 0 0 8px 0; color: {border_color}; font-size: 18px;">{severity} Alert - {brand_name}</h2>
            <p style="margin: 0; color: #666; font-size: 14px;">{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</p>
        </div>

        <div style="padding: 0 20px;">
            <h3 style="margin: 0 0 12px 0; color: #333; font-size: 16px;">Issues Detected</h3>
            <ul style="margin: 0 0 20px 0; padding-left: 20px;">
                {issues_html}
            </ul>

            <h3 style="margin: 0 0 12px 0; color: #333; font-size: 16px;">Server Metrics</h3>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px 0; color: #666;">Disk Usage</td>
                    <td style="padding: 8px 0; color: #333; text-align: right; font-weight: 600;">{disk.get('percent', 0)}% ({disk.get('used_gb', 0)}/{disk.get('total_gb', 0)} GB)</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px 0; color: #666;">Memory Usage</td>
                    <td style="padding: 8px 0; color: #333; text-align: right; font-weight: 600;">{memory.get('percent', 0)}% ({memory.get('used_mb', 0)}/{memory.get('total_mb', 0)} MB)</td>
                </tr>
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px 0; color: #666;">Swap</td>
                    <td style="padding: 8px 0; color: #333; text-align: right; font-weight: 600;">{'Enabled' if memory.get('swap_enabled') else 'NOT CONFIGURED'} ({memory.get('swap_total_mb', 0)} MB)</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #666;">Errors (last hour)</td>
                    <td style="padding: 8px 0; color: #333; text-align: right; font-weight: 600;">{error_count}</td>
                </tr>
            </table>

            <div style="text-align: center; margin: 24px 0;">
                <a href="/admin/ops" style="display: inline-block; background: #333; color: #fff; padding: 10px 24px; text-decoration: none; border-radius: 4px; font-size: 14px;">View Ops Dashboard</a>
            </div>
        </div>

        <div style="padding: 16px 20px; background: #f9f9f9; border-top: 1px solid #eee; margin-top: 20px;">
            <p style="margin: 0; color: #999; font-size: 12px;">This is an automated alert from {brand_name}. You will not receive another alert for the same issue within 6 hours.</p>
        </div>
    </div>
    """
