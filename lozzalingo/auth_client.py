"""
Auth client for Lozzalingo ecosystem services.
Copy this file into your service to validate JWTs from auth.laurence.computer.

Usage:
    from auth_client import require_auth, require_site_access, require_super_admin

    @app.route('/admin/dashboard')
    @require_auth
    def dashboard():
        return render_template('dashboard.html', user=g.auth_user)

    @app.route('/admin/settings')
    @require_site_access('fat-big-quiz', 'admin')
    def settings():
        ...

    @app.route('/super-admin')
    @require_super_admin
    def super_panel():
        ...

Environment variables:
    AUTH_SERVICE_URL  - Base URL of the auth service (default: https://auth.laurence.computer)
    AUTH_JWT_SECRET   - (DEPRECATED) HS256 shared secret. Only needed during migration.
                        New deployments should omit this; the client fetches the RS256
                        public key from the auth service's JWKS endpoint automatically.

Dependencies:
    cryptography     - for RS256 JWT verification (pip install cryptography)
"""
import os
import json
import hmac
import hashlib
import base64
import time
import threading
from functools import wraps
from flask import request, g, redirect, jsonify

# Load .env if python-dotenv is available (some apps rely on it)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'https://auth.laurence.computer')


# ---------------------------------------------------------------------------
# RS256 public key fetching and caching
# ---------------------------------------------------------------------------

_rs256_public_key = None
_rs256_public_key_lock = threading.Lock()
_rs256_last_fetch = 0
_RS256_CACHE_TTL = 3600  # Re-fetch public key every hour


def _fetch_rs256_public_key():
    """Fetch the RS256 public key from the auth service JWKS endpoint.

    Caches the key in memory for up to 1 hour. Thread-safe.
    Returns the public key object or None on failure.
    """
    global _rs256_public_key, _rs256_last_fetch

    now = time.time()
    if _rs256_public_key is not None and (now - _rs256_last_fetch) < _RS256_CACHE_TTL:
        return _rs256_public_key

    with _rs256_public_key_lock:
        # Double-check after acquiring lock
        now = time.time()
        if _rs256_public_key is not None and (now - _rs256_last_fetch) < _RS256_CACHE_TTL:
            return _rs256_public_key

        try:
            import requests as http_requests
            resp = http_requests.get(
                f'{AUTH_SERVICE_URL}/.well-known/jwks.json',
                timeout=5,
            )
            if resp.status_code != 200:
                print(f'[AUTH_CLIENT] JWKS fetch failed: {resp.status_code}')
                return _rs256_public_key  # Return stale key if available

            jwks = resp.json()
            keys = jwks.get('keys', [])
            if not keys:
                print('[AUTH_CLIENT] JWKS response has no keys')
                return _rs256_public_key

            # Use the first RS256 key
            jwk = next((k for k in keys if k.get('alg') == 'RS256'), keys[0])

            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
            from cryptography.hazmat.backends import default_backend

            def _b64url_decode(data):
                padding = 4 - len(data) % 4
                if padding != 4:
                    data += '=' * padding
                return base64.urlsafe_b64decode(data)

            n_bytes = _b64url_decode(jwk['n'])
            e_bytes = _b64url_decode(jwk['e'])
            n = int.from_bytes(n_bytes, byteorder='big')
            e = int.from_bytes(e_bytes, byteorder='big')

            pub_numbers = RSAPublicNumbers(e, n)
            _rs256_public_key = pub_numbers.public_key(default_backend())
            _rs256_last_fetch = now
            print('[AUTH_CLIENT] RS256 public key fetched and cached')
            return _rs256_public_key

        except Exception as exc:
            print(f'[AUTH_CLIENT] Failed to fetch JWKS: {exc}')
            return _rs256_public_key  # Return stale key if available


def _invalidate_rs256_cache():
    """Force a re-fetch of the RS256 public key on next verification."""
    global _rs256_last_fetch
    _rs256_last_fetch = 0


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _clean_redirect_url(url):
    """Strip any stale auth_token param from a URL and fix the scheme.

    Inside Docker containers, request.url returns http:// because Nginx
    terminates SSL. This function upgrades to https:// when X-Forwarded-Proto
    is set, preventing meta-refresh redirects to plain HTTP URLs.
    Also strips auth_token to prevent duplicate params in SSO loops.
    """
    from urllib.parse import urlencode, urlparse, parse_qs
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params.pop('auth_token', None)
    clean_query = urlencode(params, doseq=True)
    # Fix scheme: behind Nginx/Cloudflare, request.url is http but the
    # real client-facing scheme is https.
    scheme = parsed.scheme
    try:
        from flask import request as _req
        proto = _req.headers.get('X-Forwarded-Proto')
        if proto:
            scheme = proto
    except (RuntimeError, ImportError):
        pass
    return parsed._replace(scheme=scheme, query=clean_query).geturl()


# ---------------------------------------------------------------------------
# JWT secret (HS256 fallback, deprecated)
# ---------------------------------------------------------------------------

def _get_jwt_secret():
    """Get JWT secret lazily so dotenv has time to load in the host app."""
    return os.getenv('AUTH_JWT_SECRET', '')


def _b64_decode(data):
    """Decode base64url-encoded data with padding."""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += '=' * padding
    return base64.urlsafe_b64decode(data)


# ---------------------------------------------------------------------------
# JWT decoding
# ---------------------------------------------------------------------------

def decode_jwt(token):
    """
    Decode and verify a JWT token.

    Verification order:
    1. RS256 using the public key from the auth service JWKS endpoint
    2. HS256 using AUTH_JWT_SECRET (migration fallback, deprecated)

    Returns the payload dict or None if invalid/expired.
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature_b64 = parts

        # Decode header to check algorithm
        header = json.loads(_b64_decode(header_b64))
        alg = header.get('alg', '')

        # Decode payload (needed for expiry check regardless of verification method)
        payload = json.loads(_b64_decode(payload_b64))

        # Check expiry early
        exp = payload.get('exp')
        if exp and time.time() > exp:
            return None

        # Try RS256 verification
        if alg == 'RS256':
            pub_key = _fetch_rs256_public_key()
            if pub_key:
                try:
                    from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
                    from cryptography.hazmat.primitives import hashes

                    signing_input = f'{header_b64}.{payload_b64}'.encode('utf-8')
                    actual_sig = _b64_decode(signature_b64)
                    pub_key.verify(actual_sig, signing_input, asym_padding.PKCS1v15(), hashes.SHA256())
                    return payload
                except Exception:
                    # Signature invalid, try re-fetching key (might have rotated)
                    _invalidate_rs256_cache()
                    pub_key = _fetch_rs256_public_key()
                    if pub_key:
                        try:
                            pub_key.verify(actual_sig, signing_input, asym_padding.PKCS1v15(), hashes.SHA256())
                            return payload
                        except Exception:
                            pass
                    # RS256 verification failed
                    return None

        # HS256 verification (legacy fallback)
        if alg == 'HS256':
            secret = _get_jwt_secret()
            if not secret:
                return None
            signing_input = f'{header_b64}.{payload_b64}'.encode('utf-8')
            expected_sig = hmac.new(
                secret.encode('utf-8'),
                signing_input,
                hashlib.sha256
            ).digest()
            actual_sig = _b64_decode(signature_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                return None
            return payload

        # Unknown algorithm
        return None

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def get_auth_user_from_cookie():
    """Read the auth_token cookie and return the decoded JWT payload, or None.

    Useful for views that want to check auth status without requiring it.
    Does not redirect or return errors - just returns the payload or None.
    """
    token = request.cookies.get('auth_token')
    if not token:
        return None
    return decode_jwt(token)


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def require_auth(f):
    """Decorator that requires a valid JWT token (cookie, header, or query param).

    For cross-domain SSO, the auth service appends ?auth_token=<jwt> to the
    redirect URL. This decorator reads it, validates, sets a local cookie,
    and redirects to strip the token from the URL.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import make_response
        # Check for token passed via query param (cross-domain SSO)
        token_from_url = request.args.get('auth_token')
        if token_from_url:
            payload = decode_jwt(token_from_url)
            if payload:
                # Strip auth_token from URL
                clean_url = _clean_redirect_url(request.url)
                # Return an HTML page that sets the cookie via response header
                # and redirects. Using a 200 with Set-Cookie avoids Cloudflare
                # stripping cookies from 302 responses.
                html = (
                    '<!DOCTYPE html><html><head>'
                    f'<meta http-equiv="refresh" content="0;url={clean_url}">'
                    '</head><body>Redirecting...</body></html>'
                )
                resp = make_response(html, 200)
                resp.headers['Content-Type'] = 'text/html'
                resp.set_cookie(
                    'auth_token', token_from_url,
                    httponly=True, secure=True, samesite='Lax',
                    max_age=900, path='/',
                )
                return resp

        token = (
            request.cookies.get('auth_token')
            or request.headers.get('Authorization', '').replace('Bearer ', '')
        )
        if not token:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(f'{AUTH_SERVICE_URL}/login?redirect={_clean_redirect_url(request.url)}')

        payload = decode_jwt(token)
        if not payload:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'error': 'Invalid or expired token'}), 401
            return redirect(f'{AUTH_SERVICE_URL}/login?redirect={_clean_redirect_url(request.url)}')

        g.auth_user = payload
        return f(*args, **kwargs)
    return decorated


def require_site_access(site_id, min_role='viewer'):
    """
    Decorator that requires the user to have access to a specific site
    with at least the specified role.

    Role hierarchy: viewer < editor < admin < owner
    Super admins bypass all site access checks.
    """
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            user = g.auth_user
            if user.get('is_super_admin'):
                return f(*args, **kwargs)

            access = next(
                (a for a in user.get('site_access', []) if a['site_id'] == site_id),
                None
            )
            if not access:
                return jsonify({'error': 'Access denied'}), 403

            roles = ['viewer', 'editor', 'admin', 'owner']
            if roles.index(access['role']) < roles.index(min_role):
                return jsonify({'error': 'Insufficient role'}), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def require_super_admin(f):
    """Decorator that requires the user to be a super admin."""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if not g.auth_user.get('is_super_admin'):
            return jsonify({'error': 'Super admin required'}), 403
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# White-label auth proxy helpers
# ---------------------------------------------------------------------------
# These let bespoke apps proxy login/register through the centralised auth
# service without the user ever seeing auth.laurence.computer. The app keeps
# its own login page and calls these from its own backend routes.

def proxy_login(email, password):
    """Forward credentials to the auth service and return the result.

    Returns (response_dict, status_code) tuple.

    On success, response_dict contains:
        access_token, refresh_token, expires_in

    On failure, response_dict contains:
        error (string)

    Usage in a Flask route:
        @app.route('/login', methods=['POST'])
        def login():
            data = request.get_json()
            result, status = proxy_login(data['email'], data['password'])
            if status == 200:
                resp = make_response(jsonify({'success': True}))
                resp.set_cookie('auth_token', result['access_token'],
                                httponly=True, samesite='Lax', max_age=result['expires_in'])
                return resp
            return jsonify(result), status
    """
    import requests as http_requests
    try:
        resp = http_requests.post(
            f'{AUTH_SERVICE_URL}/api/auth/login',
            json={'email': email, 'password': password},
            timeout=10,
        )
        return resp.json(), resp.status_code
    except Exception as exc:
        return {'error': f'Auth service unavailable: {exc}'}, 503


def proxy_register(email, password, display_name=''):
    """Forward a registration request to the auth service.

    Returns (response_dict, status_code) tuple.

    On success (201), response_dict contains:
        user_id, message

    On failure, response_dict contains:
        error (string)

    Usage in a Flask route:
        @app.route('/register', methods=['POST'])
        def register():
            data = request.get_json()
            result, status = proxy_register(data['email'], data['password'], data.get('name', ''))
            if status == 201:
                # Create local user record for app-specific data
                create_local_user(data['email'])
                return jsonify({'success': True, 'message': result['message']})
            return jsonify(result), status
    """
    import requests as http_requests
    try:
        resp = http_requests.post(
            f'{AUTH_SERVICE_URL}/api/auth/register',
            json={'email': email, 'password': password, 'display_name': display_name},
            timeout=10,
        )
        return resp.json(), resp.status_code
    except Exception as exc:
        return {'error': f'Auth service unavailable: {exc}'}, 503
