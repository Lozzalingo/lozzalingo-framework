"""
Thin client for the centralised Payments service.
Sites call this instead of using Stripe directly.

Usage:
    from lozzalingo.clients.payments_client import PaymentsClient

    client = PaymentsClient()  # reads PAYMENTS_SERVICE_URL + PAYMENTS_API_KEY from env

    # Create checkout
    result = client.create_checkout(
        line_items=[{"name": "T-Shirt", "price_pence": 2500, "quantity": 1}],
        success_url="https://mysite.com/success",
        cancel_url="https://mysite.com/cancel",
        customer_email="buyer@example.com",
        metadata={"order_id": "123"}
    )
    # result = {"checkout_url": "https://checkout.stripe.com/...", "session_id": "cs_..."}

    # Check payment status
    status = client.get_session(session_id)

    # Get transaction history
    transactions = client.list_transactions(limit=20)
"""

import os
import hmac
import hashlib
import requests

from lozzalingo.core import db_log


class PaymentsClient:
    """Synchronous client for the centralised Payments service."""

    def __init__(self, service_url=None, api_key=None, timeout=10):
        self.url = (service_url or os.getenv('PAYMENTS_SERVICE_URL', '')).rstrip('/')
        self.key = api_key or os.getenv('PAYMENTS_API_KEY', '')
        self.timeout = timeout

        if not self.url:
            db_log('warning', 'payments_client', 'PAYMENTS_SERVICE_URL not set')
        if not self.key:
            db_log('warning', 'payments_client', 'PAYMENTS_API_KEY not set')

    def _headers(self):
        """Build request headers with authentication."""
        return {
            'Content-Type': 'application/json',
            'X-Pay-Key': self.key,
        }

    def _request(self, method, path, json_data=None, params=None):
        """Make an HTTP request to the payments service.

        Returns the parsed JSON response on success, or None on failure.
        Never raises - logs errors and returns None so the calling site
        keeps working even if the payments service is down.
        """
        if not self.url:
            db_log('error', 'payments_client', 'Cannot make request, PAYMENTS_SERVICE_URL not set')
            return None

        full_url = f'{self.url}{path}'

        try:
            response = requests.request(
                method,
                full_url,
                json=json_data,
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            db_log('error', 'payments_client', f'Request timed out: {method} {path}')
            return None
        except requests.exceptions.ConnectionError:
            db_log('error', 'payments_client', f'Connection failed: {method} {path}')
            return None
        except requests.exceptions.HTTPError as e:
            db_log('error', 'payments_client', f'HTTP error: {method} {path}', {
                'status': e.response.status_code if e.response is not None else None,
                'body': e.response.text[:500] if e.response is not None else None,
            })
            return None
        except Exception as e:
            db_log('error', 'payments_client', f'Unexpected error: {method} {path}', {
                'error': str(e),
            })
            return None

    def create_checkout(self, line_items, success_url, cancel_url,
                        customer_email=None, metadata=None, currency='gbp'):
        """Create a checkout session via the payments service.

        Args:
            line_items: List of dicts with name, price_pence, quantity.
            success_url: Redirect URL after successful payment.
            cancel_url: Redirect URL if the customer cancels.
            customer_email: Optional pre-fill email.
            metadata: Optional dict of metadata to attach.
            currency: Currency code (default: gbp).

        Returns:
            Dict with checkout_url and session_id on success, or None on failure.
        """
        payload = {
            'line_items': line_items,
            'success_url': success_url,
            'cancel_url': cancel_url,
            'currency': currency,
        }
        if customer_email:
            payload['customer_email'] = customer_email
        if metadata:
            payload['metadata'] = metadata

        return self._request('POST', '/api/payments/checkout', json_data=payload)

    def get_session(self, session_id):
        """Retrieve a checkout session by ID.

        Args:
            session_id: The Stripe session ID (cs_...).

        Returns:
            Dict with session details on success, or None on failure.
        """
        return self._request('GET', '/api/payments/session', params={'session_id': session_id})

    def list_transactions(self, limit=20, offset=0):
        """List recent transactions from the payments service.

        Args:
            limit: Number of results to return (default: 20).
            offset: Number of results to skip (default: 0).

        Returns:
            Dict with transactions list on success, or None on failure.
        """
        return self._request('GET', '/api/payments/transactions', params={
            'limit': limit,
            'offset': offset,
        })

    def verify_callback(self, request):
        """Verify that a payment callback came from the payments service.

        Checks the X-Pay-Signature header against the request body using
        the shared API key as the HMAC secret.

        Args:
            request: A Flask request object.

        Returns:
            Parsed JSON body if signature is valid, or None if invalid.
        """
        signature = request.headers.get('X-Pay-Signature', '')
        if not signature:
            db_log('warning', 'payments_client', 'Callback missing X-Pay-Signature header')
            return None

        body = request.get_data()
        expected = hmac.new(
            self.key.encode('utf-8'),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            db_log('warning', 'payments_client', 'Callback signature mismatch')
            return None

        return request.get_json(silent=True)


def create_payment_callback_blueprint(on_success, on_failure, url_prefix='/payments'):
    """Create a Flask blueprint that handles payment callbacks from the service.

    The payments service POSTs to this endpoint after a checkout completes or fails.
    Each site registers this blueprint and provides its own on_success/on_failure
    handlers to do site-specific work (update orders, send emails, etc.).

    Args:
        on_success: Callable that receives the callback data dict on successful payment.
                    Data includes: session_id, line_items, metadata, customer_email.
        on_failure: Callable that receives the callback data dict on failed/expired payment.
                    Data includes: session_id, event_type, metadata.
        url_prefix: URL prefix for the blueprint (default: /payments).

    Returns:
        A Flask Blueprint ready to register with app.register_blueprint().

    Usage:
        def handle_success(data):
            order = Order.query.get(data['metadata']['order_id'])
            order.status = 'paid'
            db.commit()
            send_confirmation_email(order)

        def handle_failure(data):
            order = Order.query.get(data['metadata']['order_id'])
            order.status = 'failed'
            db.commit()

        callback_bp = create_payment_callback_blueprint(handle_success, handle_failure)
        app.register_blueprint(callback_bp)
    """
    from flask import Blueprint, request, jsonify

    bp = Blueprint('payment_callbacks', __name__, url_prefix=url_prefix)
    client = PaymentsClient()

    @bp.route('/callback', methods=['POST'])
    def payment_callback():
        # Verify the callback signature
        data = client.verify_callback(request)
        if data is None:
            db_log('warning', 'payments_client', 'Rejected callback with invalid signature')
            return jsonify({'error': 'Invalid signature'}), 403

        event_type = data.get('event_type', '')
        session_id = data.get('session_id', '')
        metadata = data.get('metadata', {})
        line_items = data.get('line_items', [])
        customer_email = data.get('customer_email', '')

        db_log('info', 'payments_client', f'Received callback: {event_type}', {
            'session_id': session_id,
        })

        try:
            if event_type == 'checkout.session.completed':
                on_success({
                    'session_id': session_id,
                    'line_items': line_items,
                    'metadata': metadata,
                    'customer_email': customer_email,
                })
            else:
                on_failure({
                    'session_id': session_id,
                    'event_type': event_type,
                    'metadata': metadata,
                })
        except Exception as e:
            db_log('error', 'payments_client', f'Callback handler failed for {event_type}', {
                'session_id': session_id,
                'error': str(e),
            })
            # Still return 200 so the payments service does not retry for app errors
            return jsonify({'received': True, 'error': 'Handler failed'}), 200

        return jsonify({'received': True}), 200

    return bp
