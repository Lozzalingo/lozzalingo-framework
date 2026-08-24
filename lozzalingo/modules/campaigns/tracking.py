"""
Campaign Tracking Routes
========================

Public routes for email engagement tracking:
- Open tracking (1x1 transparent pixel)
- Click tracking (redirect via logged link)
- SES bounce/complaint webhook (SNS notifications)

All tracking routes are unauthenticated since they are hit from email clients.
"""

import json
import base64
import logging
import hashlib
from urllib.parse import unquote

from flask import Blueprint, request, redirect, Response, jsonify, current_app

from .models import (
    init_campaigns_db, decode_tracking_id,
    record_open, record_click, record_email_event,
    deactivate_subscriber
)

logger = logging.getLogger(__name__)

# Public blueprint - no admin auth required
campaigns_tracking_bp = Blueprint(
    'campaigns_tracking',
    __name__,
    url_prefix='/api/campaigns/track'
)


def _db_log(level, message, details=None):
    """Log to framework's persistent DB logger"""
    try:
        from lozzalingo.core import db_log
        db_log(level, 'campaigns_tracking', message, details)
    except Exception:
        pass


# 1x1 transparent GIF (smallest valid GIF89a)
TRACKING_PIXEL = base64.b64decode(
    'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
)


@campaigns_tracking_bp.route('/open/<tracking_id>')
def track_open(tracking_id):
    """Serve a 1x1 tracking pixel and log the open event.

    Called by email clients when they load images.
    Must be as lightweight as possible.
    """
    try:
        init_campaigns_db()
        campaign_id, email = decode_tracking_id(tracking_id)
        if campaign_id and email:
            record_open(campaign_id, email)
            logger.info(f"[CAMPAIGNS_TRACKING] Open: campaign={campaign_id}, email={email}")
    except Exception as e:
        # Never fail the pixel response - always return the image
        logger.error(f"[CAMPAIGNS_TRACKING] Error in open tracking: {e}")
        _db_log('error', 'Error in open tracking', {'error': str(e)})

    return Response(
        TRACKING_PIXEL,
        mimetype='image/gif',
        headers={
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Expires': '0',
        }
    )


@campaigns_tracking_bp.route('/click/<tracking_id>')
def track_click(tracking_id):
    """Log a click event and redirect to the original URL.

    The destination URL is passed as a ?url= query parameter.
    Returns a 302 redirect to the original URL.
    """
    destination = request.args.get('url', '')
    if not destination:
        return Response('Missing destination URL', status=400)

    # Decode the URL (it may be URL-encoded)
    destination = unquote(destination)

    try:
        init_campaigns_db()
        campaign_id, email = decode_tracking_id(tracking_id)
        if campaign_id and email:
            record_click(campaign_id, email, destination)
            logger.info(f"[CAMPAIGNS_TRACKING] Click: campaign={campaign_id}, url={destination}")
    except Exception as e:
        # Never block the redirect - always send the user through
        logger.error(f"[CAMPAIGNS_TRACKING] Error in click tracking: {e}")
        _db_log('error', 'Error in click tracking', {'error': str(e)})

    return redirect(destination, code=302)


@campaigns_tracking_bp.route('/ses-webhook', methods=['POST'])
def ses_webhook():
    """Handle AWS SES bounce/complaint notifications via SNS.

    Supports three SNS message types:
    - SubscriptionConfirmation: auto-confirm the SNS subscription
    - Notification: process bounce/complaint events
    - UnsubscribeConfirmation: log and acknowledge
    """
    try:
        init_campaigns_db()

        # SNS sends JSON with content-type text/plain sometimes
        if request.is_json:
            data = request.get_json()
        else:
            data = json.loads(request.data.decode('utf-8'))

        msg_type = data.get('Type', '')

        # --- SNS Subscription Confirmation ---
        if msg_type == 'SubscriptionConfirmation':
            subscribe_url = data.get('SubscribeURL')
            if subscribe_url:
                # Auto-confirm by fetching the SubscribeURL
                try:
                    import requests as http_requests
                    http_requests.get(subscribe_url, timeout=10)
                    logger.info("[CAMPAIGNS_TRACKING] SNS subscription confirmed")
                    _db_log('info', 'SNS subscription confirmed', {'topic': data.get('TopicArn')})
                except Exception as e:
                    logger.error(f"[CAMPAIGNS_TRACKING] Failed to confirm SNS subscription: {e}")
                    _db_log('error', 'Failed to confirm SNS subscription', {'error': str(e)})
            return jsonify({'status': 'confirmed'}), 200

        # --- SNS Unsubscribe Confirmation ---
        if msg_type == 'UnsubscribeConfirmation':
            logger.info("[CAMPAIGNS_TRACKING] SNS unsubscribe confirmation received")
            _db_log('info', 'SNS unsubscribe confirmation', {'topic': data.get('TopicArn')})
            return jsonify({'status': 'acknowledged'}), 200

        # --- SNS Notification ---
        if msg_type == 'Notification':
            message = data.get('Message', '')
            if isinstance(message, str):
                try:
                    message = json.loads(message)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("[CAMPAIGNS_TRACKING] Could not parse SNS message body")
                    return jsonify({'status': 'parse_error'}), 200

            notification_type = message.get('notificationType', '')

            if notification_type == 'Bounce':
                _handle_bounce(message)
            elif notification_type == 'Complaint':
                _handle_complaint(message)
            else:
                logger.info(f"[CAMPAIGNS_TRACKING] Unhandled SES notification type: {notification_type}")

            return jsonify({'status': 'processed'}), 200

        logger.warning(f"[CAMPAIGNS_TRACKING] Unknown SNS message type: {msg_type}")
        return jsonify({'status': 'unknown_type'}), 200

    except Exception as e:
        logger.error(f"[CAMPAIGNS_TRACKING] Error processing SES webhook: {e}")
        _db_log('error', 'Error processing SES webhook', {'error': str(e)})
        return jsonify({'error': 'Internal error'}), 500


def _handle_bounce(message):
    """Process an SES bounce notification. Deactivates hard-bounced recipients."""
    bounce = message.get('bounce', {})
    bounce_type = bounce.get('bounceType', 'Unknown')
    recipients = bounce.get('bouncedRecipients', [])

    for recipient in recipients:
        email = recipient.get('emailAddress', '')
        if not email:
            continue

        details = {
            'bounce_type': bounce_type,
            'bounce_sub_type': bounce.get('bounceSubType', ''),
            'diagnostic_code': recipient.get('diagnosticCode', ''),
            'action': recipient.get('action', ''),
        }

        record_email_event(email, 'bounce', details)

        # Auto-deactivate on hard bounces (permanent failures)
        if bounce_type == 'Permanent':
            deactivate_subscriber(email)
            logger.info(f"[CAMPAIGNS_TRACKING] Hard bounce - deactivated: {email}")
            _db_log('warning', f'Hard bounce - subscriber deactivated', {
                'email': email, 'diagnostic': details.get('diagnostic_code', '')
            })
        else:
            logger.info(f"[CAMPAIGNS_TRACKING] Soft bounce recorded: {email} ({bounce_type})")


def _handle_complaint(message):
    """Process an SES complaint notification (spam report). Always deactivates."""
    complaint = message.get('complaint', {})
    recipients = complaint.get('complainedRecipients', [])

    for recipient in recipients:
        email = recipient.get('emailAddress', '')
        if not email:
            continue

        details = {
            'complaint_type': complaint.get('complaintFeedbackType', ''),
            'user_agent': complaint.get('userAgent', ''),
            'arrival_date': complaint.get('arrivalDate', ''),
        }

        record_email_event(email, 'complaint', details)
        deactivate_subscriber(email)

        logger.info(f"[CAMPAIGNS_TRACKING] Spam complaint - deactivated: {email}")
        _db_log('warning', f'Spam complaint - subscriber deactivated', {
            'email': email, 'type': details.get('complaint_type', '')
        })
