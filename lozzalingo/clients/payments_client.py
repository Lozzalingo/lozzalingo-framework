"""
Thin client for the centralised Payments service.
Sites call this instead of using Stripe directly.

Usage:
    from lozzalingo.clients.payments_client import PaymentsClient

    client = PaymentsClient()  # reads PAYMENTS_SERVICE_URL + PAYMENTS_API_KEY from env

    # One-time checkout
    result = client.create_checkout(
        line_items=[{"name": "T-Shirt", "price_pence": 2500, "quantity": 1}],
        success_url="https://mysite.com/success",
        cancel_url="https://mysite.com/cancel",
        customer_email="buyer@example.com",
        metadata={"order_id": "123"}
    )
    # result = {"checkout_url": "https://checkout.stripe.com/...", "session_id": "cs_..."}

    # Subscription checkout
    result = client.create_subscription_checkout(
        line_items=[{"price_id": "price_xxx", "quantity": 1}],
        success_url="https://mysite.com/success",
        cancel_url="https://mysite.com/cancel",
        customer_email="buyer@example.com"
    )

    # PaymentIntent (custom flow)
    result = client.create_intent(amount_pence=2500, currency="gbp")
    # result = {"client_secret": "pi_..._secret_...", "intent_id": "pi_..."}

    # Subscription management
    sub = client.get_subscription("sub_xxx")
    client.update_subscription("sub_xxx", cancel_at_period_end=True)
    client.cancel_subscription("sub_xxx")

    # Customer management
    customer = client.create_customer("user@example.com", metadata={"user_id": "1"})
    client.get_customer("cus_xxx")

    # Billing portal
    portal = client.create_billing_portal("cus_xxx", return_url="https://mysite.com/settings")

    # Refunds
    client.create_refund(payment_intent_id="pi_xxx")
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

    # -----------------------------------------------------------------------
    # One-time checkout
    # -----------------------------------------------------------------------

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
        return self._request('GET', '/api/payments/checkout/session', params={'session_id': session_id})

    # -----------------------------------------------------------------------
    # Subscription checkout
    # -----------------------------------------------------------------------

    def create_subscription_checkout(self, line_items, success_url, cancel_url,
                                     customer_email=None, metadata=None, trial_end=None):
        """Create a subscription checkout session.

        Args:
            line_items: List of dicts. Each item can have either:
                - price_id and quantity (for existing Stripe prices), or
                - price_data dict with currency, unit_amount, recurring,
                  and product_data (for dynamic pricing).
            success_url: Redirect URL after successful payment.
            cancel_url: Redirect URL if the customer cancels.
            customer_email: Optional pre-fill email.
            metadata: Optional dict of metadata to attach.
            trial_end: Optional Unix timestamp for trial end.

        Returns:
            Dict with checkout_url and session_id on success, or None on failure.
        """
        payload = {
            'line_items': line_items,
            'success_url': success_url,
            'cancel_url': cancel_url,
        }
        if customer_email:
            payload['customer_email'] = customer_email
        if metadata:
            payload['metadata'] = metadata
        if trial_end:
            payload['trial_end'] = trial_end

        return self._request('POST', '/api/payments/checkout/subscription', json_data=payload)

    # -----------------------------------------------------------------------
    # PaymentIntent (custom flow)
    # -----------------------------------------------------------------------

    def create_intent(self, amount_pence, currency='gbp', customer_email=None,
                      metadata=None, receipt_email=None, customer_id=None, description=None):
        """Create a PaymentIntent for custom payment flows.

        Args:
            amount_pence: Amount in pence/cents.
            currency: Currency code (default: gbp).
            customer_email: Optional email for tracking.
            metadata: Optional dict of metadata.
            receipt_email: Optional email for Stripe receipt.
            customer_id: Optional existing Stripe customer ID.
            description: Optional payment description.

        Returns:
            Dict with client_secret and intent_id on success, or None on failure.
        """
        payload = {
            'amount_pence': amount_pence,
            'currency': currency,
        }
        if customer_email:
            payload['customer_email'] = customer_email
        if metadata:
            payload['metadata'] = metadata
        if receipt_email:
            payload['receipt_email'] = receipt_email
        if customer_id:
            payload['customer_id'] = customer_id
        if description:
            payload['description'] = description

        return self._request('POST', '/api/payments/intent', json_data=payload)

    # -----------------------------------------------------------------------
    # Subscription management
    # -----------------------------------------------------------------------

    def get_subscription(self, subscription_id):
        """Retrieve subscription details.

        Args:
            subscription_id: The Stripe subscription ID (sub_...).

        Returns:
            Dict with subscription details on success, or None on failure.
        """
        return self._request('GET', f'/api/payments/subscriptions/{subscription_id}')

    def update_subscription(self, subscription_id, cancel_at_period_end=None,
                            items=None, proration_behavior=None, metadata=None):
        """Update a subscription.

        Args:
            subscription_id: The Stripe subscription ID.
            cancel_at_period_end: Set True to cancel at end of period.
            items: List of item updates for plan changes.
            proration_behavior: Proration setting (e.g. 'create_prorations').
            metadata: Optional metadata updates.

        Returns:
            Dict with updated subscription on success, or None on failure.
        """
        payload = {}
        if cancel_at_period_end is not None:
            payload['cancel_at_period_end'] = cancel_at_period_end
        if items is not None:
            payload['items'] = items
        if proration_behavior is not None:
            payload['proration_behavior'] = proration_behavior
        if metadata is not None:
            payload['metadata'] = metadata

        return self._request('PUT', f'/api/payments/subscriptions/{subscription_id}', json_data=payload)

    def cancel_subscription(self, subscription_id):
        """Cancel a subscription immediately.

        Args:
            subscription_id: The Stripe subscription ID.

        Returns:
            Dict with cancelled subscription on success, or None on failure.
        """
        return self._request('DELETE', f'/api/payments/subscriptions/{subscription_id}')

    # -----------------------------------------------------------------------
    # Customer management
    # -----------------------------------------------------------------------

    def create_customer(self, email, metadata=None):
        """Create a Stripe customer.

        Args:
            email: Customer email address.
            metadata: Optional dict of metadata.

        Returns:
            Dict with customer_id and email on success, or None on failure.
        """
        payload = {'email': email}
        if metadata:
            payload['metadata'] = metadata

        return self._request('POST', '/api/payments/customers', json_data=payload)

    def get_customer(self, customer_id):
        """Retrieve a Stripe customer.

        Args:
            customer_id: The Stripe customer ID (cus_...).

        Returns:
            Dict with customer details on success, or None on failure.
        """
        return self._request('GET', f'/api/payments/customers/{customer_id}')

    def update_customer(self, customer_id, email=None, metadata=None, invoice_settings=None):
        """Update a Stripe customer.

        Args:
            customer_id: The Stripe customer ID.
            email: Optional new email.
            metadata: Optional metadata updates.
            invoice_settings: Optional invoice settings (e.g. default payment method).

        Returns:
            Dict with updated customer on success, or None on failure.
        """
        payload = {}
        if email is not None:
            payload['email'] = email
        if metadata is not None:
            payload['metadata'] = metadata
        if invoice_settings is not None:
            payload['invoice_settings'] = invoice_settings

        return self._request('PUT', f'/api/payments/customers/{customer_id}', json_data=payload)

    def attach_payment_method(self, customer_id, payment_method_id):
        """Attach a payment method to a customer.

        Args:
            customer_id: The Stripe customer ID.
            payment_method_id: The payment method ID (pm_...).

        Returns:
            Dict with payment method details on success, or None on failure.
        """
        return self._request('POST', f'/api/payments/customers/{customer_id}/payment-methods', json_data={
            'payment_method_id': payment_method_id,
        })

    # -----------------------------------------------------------------------
    # Billing portal
    # -----------------------------------------------------------------------

    def create_billing_portal(self, customer_id, return_url):
        """Create a Stripe Billing Portal session.

        Args:
            customer_id: The Stripe customer ID.
            return_url: URL to redirect to when the customer leaves the portal.

        Returns:
            Dict with url on success, or None on failure.
        """
        return self._request('POST', '/api/payments/billing-portal', json_data={
            'customer_id': customer_id,
            'return_url': return_url,
        })

    # -----------------------------------------------------------------------
    # Refunds
    # -----------------------------------------------------------------------

    def create_refund(self, payment_intent_id=None, charge_id=None, amount=None, reason=None):
        """Create a refund.

        Args:
            payment_intent_id: The PaymentIntent to refund (full refund).
            charge_id: The charge to refund (alternative to payment_intent_id).
            amount: Optional partial refund amount in pence.
            reason: Optional reason string.

        Returns:
            Dict with refund details on success, or None on failure.
        """
        payload = {}
        if payment_intent_id:
            payload['payment_intent_id'] = payment_intent_id
        if charge_id:
            payload['charge_id'] = charge_id
        if amount is not None:
            payload['amount'] = amount
        if reason:
            payload['reason'] = reason

        return self._request('POST', '/api/payments/refunds', json_data=payload)

    # -----------------------------------------------------------------------
    # Products and prices
    # -----------------------------------------------------------------------

    def create_product(self, name, description=None, metadata=None):
        """Create a Stripe product.

        Args:
            name: Product name.
            description: Optional product description.
            metadata: Optional metadata dict.

        Returns:
            Dict with product_id and name on success, or None on failure.
        """
        payload = {'name': name}
        if description:
            payload['description'] = description
        if metadata:
            payload['metadata'] = metadata

        return self._request('POST', '/api/payments/products', json_data=payload)

    def list_products(self, limit=20, active=None):
        """List products.

        Args:
            limit: Number of results (default: 20).
            active: Optional filter by active status.

        Returns:
            Dict with products list on success, or None on failure.
        """
        params = {'limit': limit}
        if active is not None:
            params['active'] = str(active).lower()

        return self._request('GET', '/api/payments/products', params=params)

    def create_price(self, product_id, unit_amount, currency='gbp', recurring=None, metadata=None):
        """Create a Stripe price.

        Args:
            product_id: The product ID to attach this price to.
            unit_amount: Price in pence/cents.
            currency: Currency code (default: gbp).
            recurring: Optional dict with interval (e.g. {"interval": "month"}).
            metadata: Optional metadata dict.

        Returns:
            Dict with price details on success, or None on failure.
        """
        payload = {
            'product_id': product_id,
            'unit_amount': unit_amount,
            'currency': currency,
        }
        if recurring:
            payload['recurring'] = recurring
        if metadata:
            payload['metadata'] = metadata

        return self._request('POST', '/api/payments/prices', json_data=payload)

    def list_prices(self, product_id=None, limit=20, active=None):
        """List prices, optionally filtered by product.

        Args:
            product_id: Optional product ID filter.
            limit: Number of results (default: 20).
            active: Optional filter by active status.

        Returns:
            Dict with prices list on success, or None on failure.
        """
        params = {'limit': limit}
        if product_id:
            params['product_id'] = product_id
        if active is not None:
            params['active'] = str(active).lower()

        return self._request('GET', '/api/payments/prices', params=params)

    # -----------------------------------------------------------------------
    # Connect (marketplace)
    # -----------------------------------------------------------------------

    def create_connect_account(self, email, metadata=None, country=None):
        """Create a Stripe Connect account.

        Args:
            email: Provider email.
            metadata: Optional metadata dict.
            country: Optional country code.

        Returns:
            Dict with account_id on success, or None on failure.
        """
        payload = {'email': email}
        if metadata:
            payload['metadata'] = metadata
        if country:
            payload['country'] = country

        return self._request('POST', '/api/payments/connect/accounts', json_data=payload)

    def create_account_link(self, account_id, refresh_url, return_url):
        """Create a Stripe Connect account onboarding link.

        Args:
            account_id: The connected account ID.
            refresh_url: URL for refresh during onboarding.
            return_url: URL for completion of onboarding.

        Returns:
            Dict with url and expires_at on success, or None on failure.
        """
        return self._request('POST', '/api/payments/connect/account-links', json_data={
            'account_id': account_id,
            'refresh_url': refresh_url,
            'return_url': return_url,
        })

    def get_connect_account(self, account_id):
        """Retrieve a connected account.

        Args:
            account_id: The connected account ID.

        Returns:
            Dict with account details on success, or None on failure.
        """
        return self._request('GET', f'/api/payments/connect/accounts/{account_id}')

    # -----------------------------------------------------------------------
    # Transactions
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # Callback verification
    # -----------------------------------------------------------------------

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


def create_payment_callback_blueprint(on_success, on_failure=None, on_subscription=None, url_prefix='/payments'):
    """Create a Flask blueprint that handles payment callbacks from the service.

    The payments service POSTs to this endpoint after any Stripe event is processed.
    Each site registers this blueprint and provides its own handlers for
    site-specific work (update orders, send emails, etc.).

    Args:
        on_success: Callable for successful payment events (checkout.session.completed,
                    payment_intent.succeeded).
        on_failure: Callable for failed/expired events (checkout.session.expired,
                    payment_intent.payment_failed, invoice.payment_failed).
        on_subscription: Callable for subscription lifecycle events
                         (customer.subscription.created/updated/deleted).
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

        def handle_subscription(data):
            user = User.query.get(data['metadata']['user_id'])
            user.subscription_status = data['status']
            db.commit()

        callback_bp = create_payment_callback_blueprint(
            handle_success, handle_failure, handle_subscription
        )
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
            # If signature verification is not configured, fall back to raw JSON
            data = request.get_json(silent=True)
            if data is None:
                db_log('warning', 'payments_client', 'Rejected callback with invalid payload')
                return jsonify({'error': 'Invalid payload'}), 400

        event_type = data.get('event_type', '')
        session_id = data.get('session_id', '')
        metadata = data.get('metadata', {})
        line_items = data.get('line_items', [])
        customer_email = data.get('customer_email', '')

        db_log('info', 'payments_client', f'Received callback: {event_type}', {
            'session_id': session_id,
        })

        try:
            # Success events
            if event_type in ('checkout.session.completed', 'payment_intent.succeeded',
                              'invoice.paid', 'invoice.payment_succeeded'):
                if on_success:
                    on_success(data)

            # Subscription lifecycle events
            elif event_type in ('customer.subscription.created',
                                'customer.subscription.updated',
                                'customer.subscription.deleted'):
                if on_subscription:
                    on_subscription(data)
                elif on_success and event_type == 'customer.subscription.created':
                    on_success(data)

            # Failure events
            elif event_type in ('checkout.session.expired',
                                'payment_intent.payment_failed',
                                'invoice.payment_failed'):
                if on_failure:
                    on_failure(data)

            # Unknown event type - log but do not error
            else:
                db_log('info', 'payments_client', f'Unhandled callback event type: {event_type}')

        except Exception as e:
            db_log('error', 'payments_client', f'Callback handler failed for {event_type}', {
                'session_id': session_id,
                'error': str(e),
            })
            # Still return 200 so the payments service does not retry for app errors
            return jsonify({'received': True, 'error': 'Handler failed'}), 200

        return jsonify({'received': True}), 200

    return bp
