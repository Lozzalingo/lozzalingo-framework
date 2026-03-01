"""
Campaigns Routes
================

Admin CRUD + send + trigger routes for email campaigns.
All routes require admin session except send_triggered_campaigns (called internally).
"""

import json
import time
import logging
from flask import request, jsonify, render_template, session, current_app

from . import campaigns_bp
from .models import (
    init_campaigns_db, get_campaign, get_all_campaigns, save_campaign,
    delete_campaign, record_send, increment_send_count, get_triggered_campaigns
)
from .renderer import render_campaign, resolve_variables

logger = logging.getLogger(__name__)


def _db_log(level, message, details=None):
    """Log to framework's persistent DB logger"""
    try:
        from lozzalingo.core import db_log
        db_log(level, 'campaigns', message, details)
    except Exception:
        pass


def _get_email_service():
    """Get the email service (try framework first, then local app)"""
    try:
        from lozzalingo.modules.email.email_service import email_service
        if email_service.sender_email:
            return email_service
    except (ImportError, AttributeError):
        pass
    try:
        from app.services.email_service import email_service
        return email_service
    except ImportError:
        pass
    return None


def _get_subscriber_emails():
    """Get all active subscriber emails"""
    try:
        from lozzalingo.modules.subscribers.routes import get_all_subscriber_emails
        return get_all_subscriber_emails()
    except ImportError:
        pass
    try:
        from app.blueprints.subscribers.routes import get_all_subscriber_emails
        return get_all_subscriber_emails()
    except ImportError:
        pass
    return []


def _get_subscriber_count():
    """Get active subscriber count"""
    try:
        from lozzalingo.modules.subscribers.routes import get_subscriber_count
        return get_subscriber_count()
    except ImportError:
        pass
    try:
        from app.blueprints.subscribers.routes import get_subscriber_count
        return get_subscriber_count()
    except ImportError:
        pass
    return 0


# ===================
# ADMIN ROUTES
# ===================

@campaigns_bp.route('/')
def campaign_list():
    """List all campaigns + editor page"""
    if 'admin_id' not in session:
        return _redirect_to_login()

    init_campaigns_db()
    campaigns = get_all_campaigns()
    return render_template('campaigns/editor.html', campaigns=campaigns, current_campaign=None)


@campaigns_bp.route('/editor/<int:campaign_id>')
def edit_campaign(campaign_id):
    """Edit an existing campaign"""
    if 'admin_id' not in session:
        return _redirect_to_login()

    init_campaigns_db()
    campaign = get_campaign(campaign_id)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404

    campaigns = get_all_campaigns()
    return render_template('campaigns/editor.html', campaigns=campaigns, current_campaign=campaign)


@campaigns_bp.route('/editor/new')
def new_campaign():
    """New campaign editor"""
    if 'admin_id' not in session:
        return _redirect_to_login()

    init_campaigns_db()
    campaigns = get_all_campaigns()
    blank = {
        'id': None,
        'name': '',
        'subject': '',
        'blocks': [{'type': 'paragraph', 'content': ''}],
        'is_active': True,
        'trigger': 'manual'
    }
    return render_template('campaigns/editor.html', campaigns=campaigns, current_campaign=blank)


@campaigns_bp.route('/save', methods=['POST'])
def save():
    """Create or update a campaign"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    init_campaigns_db()
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        campaign_id = save_campaign(data)
        if campaign_id:
            logger.info(f"Campaign saved: {campaign_id}")
            _db_log('info', f'Campaign saved: {data.get("name")}', {'id': campaign_id})
            return jsonify({'id': campaign_id, 'message': 'Campaign saved'}), 200
        else:
            return jsonify({'error': 'Failed to save campaign'}), 500

    except Exception as e:
        logger.error(f"Error saving campaign: {e}")
        _db_log('error', 'Error saving campaign', {'error': str(e)})
        return jsonify({'error': str(e)}), 500


@campaigns_bp.route('/preview', methods=['POST'])
def preview():
    """Render blocks to HTML for live preview"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    try:
        data = request.get_json()
        blocks = data.get('blocks', [])

        # Use preview values for variables
        preview_vars = {'EMAIL': 'subscriber@example.com', 'UNSUBSCRIBE_URL': '#'}
        custom_vars = current_app.config.get('CAMPAIGN_VARIABLES', {})
        for key, var_config in custom_vars.items():
            preview_vars[key] = var_config.get('preview_value', f'{{{{{key}}}}}')

        html = render_campaign(blocks, preview_vars)
        return jsonify({'html': html}), 200

    except Exception as e:
        logger.error(f"Error rendering preview: {e}")
        _db_log('error', 'Error rendering preview', {'error': str(e)})
        return jsonify({'error': str(e)}), 500


@campaigns_bp.route('/send/<int:campaign_id>', methods=['POST'])
def send_campaign(campaign_id):
    """Send campaign to all active subscribers"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    init_campaigns_db()
    campaign = get_campaign(campaign_id)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404

    svc = _get_email_service()
    if not svc:
        return jsonify({'error': 'Email service not configured'}), 500

    emails = _get_subscriber_emails()
    if not emails:
        return jsonify({'error': 'No active subscribers found'}), 400

    sent = 0
    failed = 0
    for email_addr in emails:
        try:
            variables = resolve_variables(email_addr)
            html = render_campaign(campaign['blocks'], variables)
            success = svc.send_email([email_addr], campaign['subject'], html)

            if success:
                record_send(campaign_id, email_addr, 'sent')
                sent += 1
            else:
                record_send(campaign_id, email_addr, 'failed', 'Provider returned failure')
                failed += 1

        except Exception as e:
            logger.error(f"Error sending campaign to {email_addr}: {e}")
            record_send(campaign_id, email_addr, 'failed', str(e))
            failed += 1

    increment_send_count(campaign_id)

    logger.info(f"Campaign {campaign_id} sent: {sent} succeeded, {failed} failed")
    _db_log('info', f'Campaign blast sent', {
        'campaign_id': campaign_id, 'sent': sent, 'failed': failed
    })

    return jsonify({
        'message': f'Campaign sent to {sent} subscribers ({failed} failed)',
        'sent': sent,
        'failed': failed
    }), 200


@campaigns_bp.route('/send-test/<int:campaign_id>', methods=['POST'])
def send_test(campaign_id):
    """Send test email to admin"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    init_campaigns_db()
    campaign = get_campaign(campaign_id)
    if not campaign:
        return jsonify({'error': 'Campaign not found'}), 404

    svc = _get_email_service()
    if not svc:
        return jsonify({'error': 'Email service not configured'}), 500

    admin_email = current_app.config.get('EMAIL_ADMIN_EMAIL') or current_app.config.get('EMAIL_ADDRESS')
    if not admin_email:
        return jsonify({'error': 'Admin email not configured'}), 500

    try:
        # Use preview values for test
        preview_vars = {'EMAIL': admin_email, 'UNSUBSCRIBE_URL': '#'}
        custom_vars = current_app.config.get('CAMPAIGN_VARIABLES', {})
        for key, var_config in custom_vars.items():
            preview_vars[key] = var_config.get('preview_value', f'{{{{{key}}}}}')

        html = render_campaign(campaign['blocks'], preview_vars)
        subject = f"[TEST] {campaign['subject']}"
        success = svc.send_email([admin_email], subject, html)

        if success:
            logger.info(f"Test email sent for campaign {campaign_id} to {admin_email}")
            _db_log('info', f'Test email sent for campaign {campaign_id}')
            return jsonify({'message': f'Test email sent to {admin_email}'}), 200
        else:
            return jsonify({'error': 'Failed to send test email'}), 500

    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        _db_log('error', 'Error sending test email', {'error': str(e)})
        return jsonify({'error': str(e)}), 500


@campaigns_bp.route('/<int:campaign_id>', methods=['DELETE'])
def delete(campaign_id):
    """Delete a campaign"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    if delete_campaign(campaign_id):
        logger.info(f"Campaign {campaign_id} deleted")
        _db_log('info', f'Campaign deleted', {'id': campaign_id})
        return jsonify({'message': 'Campaign deleted'}), 200
    else:
        return jsonify({'error': 'Failed to delete campaign'}), 500


@campaigns_bp.route('/variables')
def get_variables():
    """Return available template variables for the editor"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    variables = [
        {'key': 'EMAIL', 'description': 'Recipient email address'},
        {'key': 'UNSUBSCRIBE_URL', 'description': 'Unsubscribe page link'},
    ]

    custom_vars = current_app.config.get('CAMPAIGN_VARIABLES', {})
    for key, var_config in custom_vars.items():
        variables.append({
            'key': key,
            'description': var_config.get('description', ''),
            'preview_value': var_config.get('preview_value', '')
        })

    return jsonify({'variables': variables}), 200


@campaigns_bp.route('/subscriber-count')
def subscriber_count():
    """Return the current active subscriber count"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    count = _get_subscriber_count()
    return jsonify({'count': count}), 200


# ===================
# TRIGGERED SENDS
# ===================

def send_triggered_campaigns(email, trigger_type):
    """Send all active campaigns with matching trigger to this email.

    Called from subscriber signup flow after welcome email.
    This is a module-level function, not a route.
    """
    try:
        init_campaigns_db()
        campaigns = get_triggered_campaigns(trigger_type)

        if not campaigns:
            return

        svc = _get_email_service()
        if not svc:
            logger.warning("Cannot send triggered campaigns: email service not configured")
            return

        for campaign in campaigns:
            try:
                variables = resolve_variables(email)
                html = render_campaign(campaign['blocks'], variables)
                success = svc.send_email([email], campaign['subject'], html)

                if success:
                    record_send(campaign['id'], email, 'sent')
                    increment_send_count(campaign['id'])
                    logger.info(f"Triggered campaign '{campaign['name']}' sent to {email}")
                    _db_log('info', f"Triggered campaign sent", {
                        'campaign': campaign['name'], 'email': email, 'trigger': trigger_type
                    })
                else:
                    record_send(campaign['id'], email, 'failed', 'Provider returned failure')
                    logger.error(f"Failed to send triggered campaign '{campaign['name']}' to {email}")
                    _db_log('error', f"Failed to send triggered campaign", {
                        'campaign': campaign['name'], 'email': email
                    })

            except Exception as e:
                logger.error(f"Error sending triggered campaign '{campaign.get('name')}' to {email}: {e}")
                _db_log('error', f"Error sending triggered campaign", {
                    'campaign': campaign.get('name'), 'email': email, 'error': str(e)
                })

    except Exception as e:
        logger.error(f"Error in send_triggered_campaigns: {e}")
        _db_log('error', 'Error in send_triggered_campaigns', {'error': str(e)})


# ===================
# HELPERS
# ===================

def _redirect_to_login():
    """Redirect to admin login page"""
    from flask import redirect, url_for
    try:
        return redirect(url_for('dashboard.admin_page'))
    except Exception:
        return redirect('/admin')
