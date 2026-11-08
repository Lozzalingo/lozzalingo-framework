"""
API Docs Routes
===============

Parses the host app's ``openapi.yaml`` and serves a rendered documentation
page. Supports ``$ref`` resolution for schemas, parameters, and responses.
"""

import os
import yaml
from flask import render_template, jsonify, current_app
from . import api_docs_bp


def _load_spec():
    """Load and return the OpenAPI spec dict from the host app root."""
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
                print(f'[API_DOCS] Failed to parse {path}: {exc}')
                return None
    return None


def _resolve_ref(spec, ref_str):
    """Resolve a $ref string like '#/components/schemas/Error' into the actual object."""
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
    """Recursively resolve all $ref pointers in a dict/list."""
    if isinstance(obj, dict):
        if '$ref' in obj:
            resolved = _resolve_ref(spec, obj['$ref'])
            return _resolve_deep(spec, resolved)
        return {k: _resolve_deep(spec, v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_deep(spec, item) for item in obj]
    return obj


def _build_example_from_schema(schema):
    """Build an example JSON value from an OpenAPI schema definition."""
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


def _parse_endpoints(spec):
    """Parse the OpenAPI spec into a structured list of endpoint groups."""
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
            params = details.get('parameters', [])
            parsed_params = []
            for p in params:
                p = _resolve_deep(spec, p)
                parsed_params.append({
                    'name': p.get('name', ''),
                    'in': p.get('in', 'query'),
                    'required': p.get('required', False),
                    'description': p.get('description', ''),
                    'type': p.get('schema', {}).get('type', 'string'),
                    'default': p.get('schema', {}).get('default'),
                })

            # Parse request body
            request_body = None
            rb = details.get('requestBody')
            if rb:
                rb = _resolve_deep(spec, rb)
                content = rb.get('content', {})
                json_content = content.get('application/json', {})
                schema = json_content.get('schema', {})
                request_body = {
                    'required': rb.get('required', False),
                    'schema': schema,
                    'example': _build_example_from_schema(schema),
                    'properties': schema.get('properties', {}),
                    'required_fields': schema.get('required', []),
                }

            # Parse responses
            responses = []
            for status_code, resp in details.get('responses', {}).items():
                resp = _resolve_deep(spec, resp)
                resp_content = resp.get('content', {})
                json_resp = resp_content.get('application/json', {})
                resp_schema = json_resp.get('schema', {})
                responses.append({
                    'status': str(status_code),
                    'description': resp.get('description', ''),
                    'schema': resp_schema,
                    'example': _build_example_from_schema(resp_schema),
                })

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
                'parameters': parsed_params,
                'request_body': request_body,
                'responses': responses,
                'auth_types': auth_types,
                'deprecated': details.get('deprecated', False),
            })

    # Preserve tag ordering from the spec
    ordered_tags = [t['name'] for t in spec.get('tags', [])]
    result = []
    for tag_name in ordered_tags:
        if tag_name in groups:
            result.append(groups.pop(tag_name))
    # Append any remaining groups not in the tags list
    for group in groups.values():
        result.append(group)

    return result


@api_docs_bp.route('/')
def docs_page():
    """Render the API documentation page."""
    spec = _load_spec()
    if not spec:
        return render_template('api_docs/docs.html',
                               spec=None, groups=[], info={}, servers=[])

    info = spec.get('info', {})
    servers = spec.get('servers', [])
    groups = _parse_endpoints(spec)

    # Extract security scheme descriptions
    security_schemes = {}
    components = spec.get('components', {})
    for name, scheme in components.get('securitySchemes', {}).items():
        security_schemes[name] = {
            'type': scheme.get('type', ''),
            'name': scheme.get('name', ''),
            'in': scheme.get('in', ''),
            'description': scheme.get('description', ''),
            'scheme': scheme.get('scheme', ''),
        }

    return render_template('api_docs/docs.html',
                           spec=spec,
                           groups=groups,
                           info=info,
                           servers=servers,
                           security_schemes=security_schemes)


@api_docs_bp.route('/spec')
def docs_spec():
    """Return the raw OpenAPI spec as JSON."""
    spec = _load_spec()
    if not spec:
        return jsonify({'error': 'No OpenAPI spec found'}), 404
    return jsonify(spec)
