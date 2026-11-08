"""
API Playground Routes
=====================

Serves the playground page and provides a proxy endpoint so the browser
can make requests to the local API without CORS issues.
"""

import os
import json
import yaml
import requests as http_requests
from flask import render_template, request, jsonify, current_app
from . import api_playground_bp


def _load_spec():
    """Load the OpenAPI spec from the host app root."""
    candidates = [
        os.path.join(current_app.root_path, 'openapi.yaml'),
        os.path.join(current_app.root_path, 'openapi.yml'),
        os.path.join(os.getcwd(), 'openapi.yaml'),
        os.path.join(os.getcwd(), 'openapi.yml'),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as exc:
                print(f'[API_PLAYGROUND] Failed to parse {path}: {exc}')
                return None
    return None


def _resolve_ref(spec, ref_str):
    """Resolve a $ref string into the actual object."""
    if not ref_str or not ref_str.startswith('#/'):
        return {}
    parts = ref_str.lstrip('#/').split('/')
    obj = spec
    for part in parts:
        if isinstance(obj, dict):
            obj = obj.get(part, {})
        else:
            return {}
    return obj


def _resolve_deep(spec, obj):
    """Recursively resolve all $ref pointers."""
    if isinstance(obj, dict):
        if '$ref' in obj:
            resolved = _resolve_ref(spec, obj['$ref'])
            return _resolve_deep(spec, resolved)
        return {k: _resolve_deep(spec, v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_deep(spec, item) for item in obj]
    return obj


def _build_example_from_schema(schema):
    """Build an example JSON value from an OpenAPI schema."""
    if not schema or not isinstance(schema, dict):
        return None

    if 'example' in schema:
        return schema['example']

    schema_type = schema.get('type', 'object')

    if schema_type == 'object':
        props = schema.get('properties', {})
        if not props:
            return {}
        result = {}
        for key, prop in props.items():
            result[key] = _build_example_from_schema(prop)
        return result
    elif schema_type == 'array':
        items = schema.get('items', {})
        return [_build_example_from_schema(items)]
    elif schema_type == 'string':
        if schema.get('format') == 'email':
            return 'user@example.com'
        if schema.get('format') == 'date-time':
            return '2025-01-15T10:30:00Z'
        if 'enum' in schema:
            return schema['enum'][0]
        return schema.get('example', 'string')
    elif schema_type == 'integer':
        return schema.get('example', 0)
    elif schema_type == 'number':
        return schema.get('example', 0.0)
    elif schema_type == 'boolean':
        return schema.get('example', True)
    return None


def _parse_endpoints_for_playground(spec):
    """Parse endpoints into a JSON-safe structure for the playground JS."""
    if not spec:
        return []

    paths = spec.get('paths', {})
    tags_info = {t['name']: t.get('description', '') for t in spec.get('tags', [])}
    groups = {}

    for path, methods in paths.items():
        for method, details in methods.items():
            if method in ('parameters', 'servers', 'summary', 'description'):
                continue

            details = _resolve_deep(spec, details)
            tag_list = details.get('tags', ['Untagged'])
            tag = tag_list[0] if tag_list else 'Untagged'

            if tag not in groups:
                groups[tag] = {
                    'name': tag,
                    'description': tags_info.get(tag, ''),
                    'endpoints': [],
                }

            # Parse parameters
            params = []
            for p in details.get('parameters', []):
                p = _resolve_deep(spec, p)
                params.append({
                    'name': p.get('name', ''),
                    'in': p.get('in', 'query'),
                    'required': p.get('required', False),
                    'description': p.get('description', ''),
                    'type': p.get('schema', {}).get('type', 'string'),
                    'default': p.get('schema', {}).get('default'),
                    'enum': p.get('schema', {}).get('enum'),
                })

            # Parse request body
            request_body = None
            rb = details.get('requestBody')
            if rb:
                rb = _resolve_deep(spec, rb)
                content = rb.get('content', {})
                json_content = content.get('application/json', {})
                schema = json_content.get('schema', {})
                example = _build_example_from_schema(schema)
                properties = []
                for field_name, field in schema.get('properties', {}).items():
                    properties.append({
                        'name': field_name,
                        'type': field.get('type', 'string'),
                        'required': field_name in schema.get('required', []),
                        'description': field.get('description', ''),
                        'default': field.get('default'),
                        'enum': field.get('enum'),
                        'format': field.get('format', ''),
                        'minLength': field.get('minLength'),
                    })
                request_body = {
                    'required': rb.get('required', False),
                    'properties': properties,
                    'example': example,
                }

            # Parse security
            security = details.get('security', [])
            auth_types = []
            for sec in security:
                auth_types.extend(sec.keys())

            groups[tag]['endpoints'].append({
                'method': method.upper(),
                'path': path,
                'summary': details.get('summary', ''),
                'description': details.get('description', ''),
                'operation_id': details.get('operationId', ''),
                'parameters': params,
                'request_body': request_body,
                'auth_types': auth_types,
            })

    # Order by spec tags
    ordered_tags = [t['name'] for t in spec.get('tags', [])]
    result = []
    for tag_name in ordered_tags:
        if tag_name in groups:
            result.append(groups.pop(tag_name))
    for group in groups.values():
        result.append(group)

    return result


@api_playground_bp.route('/')
def playground_page():
    """Render the API playground page."""
    spec = _load_spec()
    servers = []
    groups = []

    if spec:
        servers = spec.get('servers', [])
        groups = _parse_endpoints_for_playground(spec)

    return render_template('api_playground/playground.html',
                           servers=servers,
                           groups_json=json.dumps(groups, default=str),
                           servers_json=json.dumps(servers, default=str))


@api_playground_bp.route('/proxy', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def proxy():
    """
    Proxy requests to the API so the playground can make calls without
    CORS issues. The target URL is passed via X-Target-URL header.
    """
    target_url = request.headers.get('X-Target-URL')
    if not target_url:
        return jsonify({'error': 'X-Target-URL header is required'}), 400

    # Security: only allow requests to known servers or localhost
    allowed_prefixes = ['http://localhost:', 'http://127.0.0.1:', 'https://']
    if not any(target_url.startswith(p) for p in allowed_prefixes):
        return jsonify({'error': 'Target URL not allowed'}), 403

    # Forward headers (exclude hop-by-hop and internal ones)
    skip_headers = {
        'host', 'x-target-url', 'content-length', 'transfer-encoding',
        'connection', 'keep-alive',
    }
    forward_headers = {}
    for key, val in request.headers:
        if key.lower() not in skip_headers:
            forward_headers[key] = val

    try:
        resp = http_requests.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            data=request.get_data(),
            timeout=30,
            allow_redirects=False,
        )

        # Build response
        excluded_resp_headers = {'transfer-encoding', 'content-encoding', 'connection'}
        response_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in excluded_resp_headers
        }

        from flask import make_response
        proxy_resp = make_response(resp.content, resp.status_code)
        for k, v in response_headers.items():
            proxy_resp.headers[k] = v

        # Add timing info
        proxy_resp.headers['X-Proxy-Time-Ms'] = str(int(resp.elapsed.total_seconds() * 1000))

        return proxy_resp

    except http_requests.exceptions.ConnectionError:
        return jsonify({'error': 'Could not connect to the target server'}), 502
    except http_requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out'}), 504
    except Exception as exc:
        print(f'[API_PLAYGROUND] Proxy error: {exc}')
        return jsonify({'error': str(exc)}), 500
