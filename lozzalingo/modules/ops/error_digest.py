"""
Daily Error Digest
==================

Sends a daily email summary of ERROR and CRITICAL level logs from app_logs.
Runs at 21:00 London time by default. Only sends if there are errors to report.

Auto-starts when both the ops and email features are enabled.
Called from _setup_error_digest() in lozzalingo/__init__.py.

Config:
    ERROR_DIGEST_RECIPIENT  - email address (defaults to EMAIL_ADMIN_EMAIL or laurencedotcomputer@gmail.com)
    ERROR_DIGEST_HOUR       - hour to send in Europe/London timezone (default 21)
    ERROR_DIGEST_ENABLED    - set to False to disable (default True)
"""

import json
import os
import threading
import time as _time
from datetime import datetime, timedelta, timezone

from flask import Flask


# Guard against double-sends within the same day
_last_digest_date = None
_digest_lock = threading.Lock()


def start_error_digest(app: Flask):
    """Start the background error digest thread.

    Checks hourly whether it's time to send the digest.
    Runs as a daemon thread so it dies with the app.
    """
    enabled = app.config.get('ERROR_DIGEST_ENABLED', True)
    if not enabled:
        print("[ErrorDigest] Disabled via ERROR_DIGEST_ENABLED=False")
        return

    def _digest_loop():
        global _last_digest_date

        while True:
            try:
                _time.sleep(3600)  # Check every hour

                with app.app_context():
                    target_hour = app.config.get('ERROR_DIGEST_HOUR', 21)

                    # Get current hour in Europe/London
                    try:
                        from zoneinfo import ZoneInfo
                        london_now = datetime.now(ZoneInfo('Europe/London'))
                    except ImportError:
                        # Python < 3.9 fallback: assume UTC+0/+1 roughly
                        london_now = datetime.now(timezone.utc)

                    current_hour = london_now.hour
                    today_str = london_now.strftime('%Y-%m-%d')

                    if current_hour != target_hour:
                        continue

                    with _digest_lock:
                        if _last_digest_date == today_str:
                            continue
                        _last_digest_date = today_str

                    print(f"[ErrorDigest] Sending daily error digest for {today_str}")
                    send_error_digest(app)

            except Exception as e:
                print(f"[ErrorDigest] Loop error: {e}")

    thread = threading.Thread(target=_digest_loop, name='error-digest', daemon=True)
    thread.start()
    print("[ErrorDigest] Background digest thread started")


def send_error_digest(app: Flask, hours_back=None):
    """Send the error digest email.

    Args:
        app: Flask application instance
        hours_back: Override number of hours to look back (default: since start of today)
    """
    with app.app_context():
        try:
            from lozzalingo.core.database import Database
            from lozzalingo.core.config import Config

            # Resolve DB path (3-tier)
            db_path = app.config.get('ANALYTICS_DB')
            if not db_path and hasattr(Config, 'ANALYTICS_DB'):
                db_path = Config.ANALYTICS_DB
            if not db_path:
                db_path = os.getenv('ANALYTICS_DB', '')

            if not db_path or not os.path.exists(db_path):
                print("[ErrorDigest] No analytics DB found, skipping")
                return

            # Calculate time window
            if hours_back:
                cutoff = (datetime.now() - timedelta(hours=hours_back)).isoformat()
            else:
                # Since start of today (London time)
                try:
                    from zoneinfo import ZoneInfo
                    london_now = datetime.now(ZoneInfo('Europe/London'))
                    start_of_today = london_now.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    cutoff = start_of_today.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
                except ImportError:
                    cutoff = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ).isoformat()

            # Query ERROR and CRITICAL logs
            with Database.connect(db_path) as conn:
                cursor = conn.cursor()

                # Check app_logs table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='app_logs'"
                )
                if not cursor.fetchone():
                    print("[ErrorDigest] app_logs table does not exist, skipping")
                    return

                cursor.execute("""
                    SELECT timestamp, level, source, message, details
                    FROM app_logs
                    WHERE level IN ('error', 'critical', 'ERROR', 'CRITICAL')
                    AND timestamp >= ?
                    ORDER BY timestamp DESC
                """, (cutoff,))

                errors = []
                for row in cursor.fetchall():
                    errors.append({
                        'timestamp': row[0],
                        'level': (row[1] or '').upper(),
                        'source': row[2] or 'unknown',
                        'message': row[3] or '',
                        'details': row[4] or '',
                    })

            if not errors:
                print("[ErrorDigest] No errors today, skipping email")
                return

            # Count by severity
            critical_count = sum(1 for e in errors if e['level'] == 'CRITICAL')
            error_count = len(errors) - critical_count

            # Resolve recipient
            recipient = (
                app.config.get('ERROR_DIGEST_RECIPIENT')
                or app.config.get('EMAIL_ADMIN_EMAIL')
                or os.getenv('ADMIN_EMAIL', 'laurencedotcomputer@gmail.com')
            )

            brand_name = app.config.get('EMAIL_BRAND_NAME', 'Lozzalingo Site')

            # Build subject
            parts = []
            if error_count:
                parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
            if critical_count:
                parts.append(f"{critical_count} critical")

            today_label = datetime.now().strftime('%d %b')
            subject = f"[{brand_name}] Error Digest: {', '.join(parts)} - {today_label}"

            # Build HTML email
            html = _build_digest_html(brand_name, errors, critical_count, error_count)

            # Send via EmailService
            from lozzalingo.modules.email.email_service import EmailService
            email_svc = EmailService()
            email_svc.init_app(app)
            email_svc.send_email([recipient], subject, html)

            print(f"[ErrorDigest] Sent digest to {recipient}: "
                  f"{error_count} errors, {critical_count} critical")

            # Log that we sent the digest
            try:
                from lozzalingo.core import db_log
                db_log('info', 'error_digest', f'Daily digest sent: {len(errors)} issues', {
                    'recipient': recipient,
                    'error_count': error_count,
                    'critical_count': critical_count,
                })
            except Exception:
                pass

        except Exception as e:
            print(f"[ErrorDigest] Failed to send digest: {e}")
            try:
                from lozzalingo.core import db_log
                db_log('error', 'error_digest', 'Failed to send daily digest', {
                    'error': str(e)
                })
            except Exception:
                pass


def _build_digest_html(brand_name, errors, critical_count, error_count):
    """Build the HTML email body for the error digest."""
    total = len(errors)
    today_label = datetime.now().strftime('%d %B %Y')

    # Summary box
    summary_bg = '#fff5f5' if critical_count else '#fffbeb'
    summary_border = '#dc3545' if critical_count else '#ffc107'

    summary_parts = []
    if error_count:
        summary_parts.append(f'<span style="color: #e67700;">{error_count} Error{"s" if error_count != 1 else ""}</span>')
    if critical_count:
        summary_parts.append(f'<span style="color: #dc3545;">{critical_count} Critical</span>')

    # Group errors by source
    by_source = {}
    for e in errors:
        src = e['source']
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(e)

    # Build source sections
    source_sections = ''
    for source, source_errors in sorted(by_source.items()):
        rows = ''
        for e in source_errors:
            # Parse time
            try:
                ts = datetime.fromisoformat(e['timestamp'])
                time_str = ts.strftime('%H:%M:%S')
            except Exception:
                time_str = e['timestamp'][:8] if e['timestamp'] else ''

            is_critical = e['level'] == 'CRITICAL'
            row_bg = 'background: #fff0f0;' if is_critical else ''
            level_color = '#dc3545' if is_critical else '#e67700'

            # Truncate details
            details = e['details']
            if details:
                try:
                    parsed = json.loads(details)
                    details = json.dumps(parsed, indent=2)
                except Exception:
                    pass
                if len(details) > 200:
                    details = details[:200] + '...'

            details_cell = ''
            if details:
                details_cell = f'<div style="font-size: 11px; color: #888; margin-top: 4px; font-family: monospace; word-break: break-all;">{details}</div>'

            rows += f'''
            <tr style="{row_bg} border-bottom: 1px solid #f0f0f0;">
                <td style="padding: 8px 12px; font-size: 13px; color: #666; white-space: nowrap; vertical-align: top;">{time_str}</td>
                <td style="padding: 8px 12px; font-size: 13px; vertical-align: top;">
                    <span style="color: {level_color}; font-weight: 600;">{e['level']}</span>
                </td>
                <td style="padding: 8px 12px; font-size: 13px; color: #333; vertical-align: top;">
                    {e['message']}{details_cell}
                </td>
            </tr>
            '''

        source_sections += f'''
        <div style="margin-bottom: 24px;">
            <h3 style="margin: 0 0 8px 0; color: #333; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">
                {source} <span style="color: #999; font-weight: normal;">({len(source_errors)})</span>
            </h3>
            <table style="width: 100%; border-collapse: collapse; border: 1px solid #eee; border-radius: 4px;">
                <thead>
                    <tr style="background: #f8f8f8;">
                        <th style="padding: 6px 12px; text-align: left; font-size: 11px; color: #999; font-weight: 600; text-transform: uppercase;">Time</th>
                        <th style="padding: 6px 12px; text-align: left; font-size: 11px; color: #999; font-weight: 600; text-transform: uppercase;">Level</th>
                        <th style="padding: 6px 12px; text-align: left; font-size: 11px; color: #999; font-weight: 600; text-transform: uppercase;">Message</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        '''

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px; margin: 0 auto;">
        <div style="background: {summary_bg}; border-left: 4px solid {summary_border}; padding: 16px 20px; margin-bottom: 24px;">
            <h2 style="margin: 0 0 4px 0; color: #333; font-size: 18px;">Error Digest - {brand_name}</h2>
            <p style="margin: 0 0 8px 0; color: #666; font-size: 13px;">{today_label}</p>
            <p style="margin: 0; font-size: 15px;">{' / '.join(summary_parts)} across {len(by_source)} source{'s' if len(by_source) != 1 else ''}</p>
        </div>

        <div style="padding: 0 4px;">
            {source_sections}
        </div>

        <div style="padding: 16px 20px; background: #f9f9f9; border-top: 1px solid #eee; margin-top: 20px;">
            <p style="margin: 0; color: #999; font-size: 12px;">
                This is an automated daily error digest from {brand_name}.
                Covers errors logged since midnight (Europe/London timezone).
            </p>
        </div>
    </div>
    """
