#!/usr/bin/env python3
"""
CRM Schema Sync Validator

Validates that all CRM implementations (JS Prisma schemas, Python SQLite schemas)
match the canonical schema definition at docs/crm-schema.md.

Usage:
    python scripts/crm-schema-sync.py              # check all
    python scripts/crm-schema-sync.py --verbose     # show all fields, not just diffs
    python scripts/crm-schema-sync.py --fix         # auto-update canonical doc from drift report

Exit codes:
    0 = all in sync
    1 = drift detected
    2 = missing implementations
"""

import os
import re
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# ---- Config ----------------------------------------------------------------

ECOSYSTEM_ROOT = Path(__file__).resolve().parents[3]  # lozzalingo-ecosystem/

CANONICAL_SCHEMA = ECOSYSTEM_ROOT / "lozzalingo-python" / "lozzalingo-framework" / "docs" / "crm-schema.md"

# JS sites with Prisma schemas
JS_SCHEMAS = {
    "BucketRace": ECOSYSTEM_ROOT / "lozzalingo-js" / "bucketrace" / "server" / "prisma" / "schema.prisma",
    "Fat Big Quiz": ECOSYSTEM_ROOT / "lozzalingo-js" / "fat-big-quiz" / "server" / "prisma" / "schema.prisma",
}

# Python sites with SQLite databases (add as they're built)
PY_DATABASES = {
    # "Crowd Sauced": ECOSYSTEM_ROOT / "lozzalingo-python" / "crowd_sauced" / "databases" / "users.db",
    # "Coffee Goblin": ECOSYSTEM_ROOT / "lozzalingo-python" / "coffee-goblin" / "databases" / "users.db",
}

# CRM tables and their expected fields (canonical, camelCase)
# This is parsed from crm-schema.md but we also keep a hardcoded fallback
CRM_TABLES = {
    "Customer": "customers",
    "CustomerActivity": "customer_activities",
    "CustomerScore": "customer_scores",
    "MarketingPreference": "marketing_preferences",
    "Campaign": "campaigns",
    "CampaignSend": "campaign_sends",
    "SubscriberConfirmation": "subscriber_confirmations",
}

# ---- Colours ----------------------------------------------------------------

class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


# ---- Parse canonical schema -------------------------------------------------

def parse_canonical_schema(path):
    """Parse crm-schema.md and extract table definitions."""
    if not path.exists():
        print(f"{C.RED}Canonical schema not found: {path}{C.RESET}")
        return {}

    content = path.read_text()
    tables = {}
    current_table = None

    for line in content.split("\n"):
        # Detect table headers like "## Customer" or "## CustomerActivity"
        header_match = re.match(r"^## (\w+)$", line.strip())
        if header_match:
            name = header_match.group(1)
            if name in CRM_TABLES:
                current_table = name
                tables[current_table] = {"fields": [], "js_fields": [], "py_fields": []}
                continue

        # Parse table rows: | Field | JS Name | Python Name | Type | ...
        if current_table and line.strip().startswith("|") and "---" not in line:
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 4 and cols[0] != "Field":
                field_name = cols[0]
                js_name = cols[1] if len(cols) > 1 else ""
                py_name = cols[2] if len(cols) > 2 else ""
                field_type = cols[3] if len(cols) > 3 else ""

                if js_name and js_name != "-":
                    tables[current_table]["fields"].append(field_name)
                    tables[current_table]["js_fields"].append(js_name)
                    tables[current_table]["py_fields"].append(py_name)

    return tables


# ---- Parse Prisma schema ----------------------------------------------------

def parse_prisma_model(schema_path, model_name):
    """Extract field names from a Prisma model definition."""
    if not schema_path.exists():
        return None

    content = schema_path.read_text()

    # Find the model block
    # Prefer CRM-prefixed models (FBQ uses CrmCampaign to avoid clash)
    search_names = [model_name]
    if model_name == "Campaign":
        search_names = ["CrmCampaign", "Campaign"]
    if model_name == "CampaignSend":
        search_names = ["CrmCampaignSend", "CampaignSend"]

    for name in search_names:
        # Use a smarter regex that handles } inside comments
        # Find "model Name {" then capture until a "}" at the start of a line
        pattern = rf"model\s+{name}\s*\{{"
        match = re.search(pattern, content)
        if match:
            start = match.end()
            # Find the closing brace: track depth, only count braces
            # that aren't inside comments
            depth = 1
            pos = start
            while pos < len(content) and depth > 0:
                ch = content[pos]
                # Skip rest of line if we hit a comment
                if ch == "/" and pos + 1 < len(content) and content[pos + 1] == "/":
                    while pos < len(content) and content[pos] != "\n":
                        pos += 1
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        break
                pos += 1
            body = content[start:pos]
            fields = []
            for line in body.strip().split("\n"):
                line = line.strip()
                # Skip comments, blank lines, relations (@@), and relation fields
                if not line or line.startswith("//") or line.startswith("@@"):
                    continue
                # Skip relation-only fields (e.g. "customer Customer @relation(...)")
                parts = line.split()
                if len(parts) >= 2:
                    field_name = parts[0]
                    field_type = parts[1]
                    # Skip if field type starts with uppercase and is a relation
                    # (but keep enums like CustomerStatus, BookingStatus)
                    if field_type.rstrip("?").rstrip("[]") in [
                        "Customer", "Booking", "Invoice", "Campaign", "CampaignSend",
                        "CrmCampaign", "CrmCampaignSend", "CustomerActivity",
                        "CustomerScore", "MarketingPreference", "SubscriberConfirmation",
                        "Visitor", "CalendarBooking",
                    ]:
                        continue
                    # Skip array relations
                    if field_type.endswith("[]"):
                        continue
                    fields.append(field_name)
            return fields

    return None


# ---- Parse SQLite schema -----------------------------------------------------

def parse_sqlite_table(db_path, table_name):
    """Extract column names from a SQLite table."""
    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return columns if columns else None
    except Exception as e:
        print(f"  {C.RED}Error reading {db_path}: {e}{C.RESET}")
        return None


# ---- Comparison logic --------------------------------------------------------

def camel_to_snake(name):
    """Convert camelCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def compare_fields(canonical_fields, actual_fields, label, is_python=False):
    """Compare canonical fields against actual implementation."""
    if actual_fields is None:
        return {"status": "missing", "missing": [], "extra": []}

    # Normalise for comparison
    if is_python:
        expected = set(canonical_fields)  # Already snake_case
    else:
        expected = set(canonical_fields)  # Already camelCase

    actual = set(actual_fields)

    missing = expected - actual
    extra = actual - expected

    if not missing and not extra:
        return {"status": "ok", "missing": [], "extra": []}
    else:
        return {"status": "drift", "missing": sorted(missing), "extra": sorted(extra)}


# ---- Main -------------------------------------------------------------------

def main():
    verbose = "--verbose" in sys.argv
    has_drift = False
    has_missing = False

    print(f"\n{C.BOLD}CRM Schema Sync Validator{C.RESET}")
    print(f"{C.DIM}Canonical schema: {CANONICAL_SCHEMA}{C.RESET}\n")

    # Parse canonical
    canonical = parse_canonical_schema(CANONICAL_SCHEMA)
    if not canonical:
        print(f"{C.RED}Failed to parse canonical schema. Aborting.{C.RESET}")
        sys.exit(2)

    print(f"{C.BLUE}Canonical schema:{C.RESET} {len(canonical)} tables defined")
    for table, info in canonical.items():
        print(f"  {table}: {len(info['js_fields'])} fields")
    print()

    # Check JS implementations
    print(f"{C.BOLD}JavaScript Implementations{C.RESET}")
    print("-" * 50)

    for site_name, schema_path in JS_SCHEMAS.items():
        print(f"\n{C.BLUE}{site_name}{C.RESET} ({schema_path.name})")

        if not schema_path.exists():
            print(f"  {C.RED}Schema file not found{C.RESET}")
            has_missing = True
            continue

        all_ok = True
        for table_name, info in canonical.items():
            js_fields = info["js_fields"]
            actual = parse_prisma_model(schema_path, table_name)

            if actual is None:
                # Some tables might have alternative names
                print(f"  {C.YELLOW}{table_name}{C.RESET}: not found (may use alternative model name)")
                continue

            result = compare_fields(js_fields, actual, f"{site_name}/{table_name}")

            if result["status"] == "ok":
                if verbose:
                    print(f"  {C.GREEN}{table_name}{C.RESET}: {len(js_fields)} fields - OK")
            elif result["status"] == "drift":
                # Missing fields = real drift, extra fields = site-specific additions (OK)
                if result["missing"]:
                    all_ok = False
                    has_drift = True
                    print(f"  {C.RED}{table_name}{C.RESET}: MISSING FIELDS")
                    print(f"    Missing from implementation: {C.RED}{', '.join(result['missing'])}{C.RESET}")
                if result["extra"]:
                    if verbose:
                        print(f"  {C.YELLOW}{table_name}{C.RESET}: {len(js_fields)} canonical + {len(result['extra'])} site-specific")
                        print(f"    Extra (site-specific): {C.DIM}{', '.join(result['extra'])}{C.RESET}")
                    elif not result["missing"]:
                        if verbose:
                            print(f"  {C.GREEN}{table_name}{C.RESET}: {len(js_fields)} fields - OK (+ {len(result['extra'])} site-specific)")
            else:
                print(f"  {C.YELLOW}{table_name}{C.RESET}: model not found")

        if all_ok and not verbose:
            print(f"  {C.GREEN}All tables in sync{C.RESET}")

    # Check cross-JS consistency
    print(f"\n{C.BOLD}Cross-Site Consistency (JS){C.RESET}")
    print("-" * 50)

    js_schemas = {}
    for site_name, schema_path in JS_SCHEMAS.items():
        if schema_path.exists():
            js_schemas[site_name] = {}
            for table_name in canonical:
                fields = parse_prisma_model(schema_path, table_name)
                if fields:
                    js_schemas[site_name][table_name] = set(fields)

    site_names = list(js_schemas.keys())
    cross_site_drift = False
    if len(site_names) >= 2:
        for table_name in canonical:
            # Only compare canonical fields across sites (not site-specific extras)
            canonical_fields = set(canonical[table_name]["js_fields"])
            fields_per_site = {}
            for site_name in site_names:
                if table_name in js_schemas[site_name]:
                    # Intersect with canonical to only compare CRM fields
                    site_canonical = js_schemas[site_name][table_name] & canonical_fields
                    fields_per_site[site_name] = site_canonical

            if len(fields_per_site) >= 2:
                all_fields = list(fields_per_site.values())
                if all(f == all_fields[0] for f in all_fields):
                    if verbose:
                        print(f"  {C.GREEN}{table_name}{C.RESET}: canonical fields identical across {len(fields_per_site)} sites")
                else:
                    cross_site_drift = True
                    has_drift = True
                    print(f"  {C.RED}{table_name}{C.RESET}: canonical fields differ between sites")
                    for site, fields in fields_per_site.items():
                        missing = canonical_fields - fields
                        if missing:
                            print(f"    {site} missing: {C.RED}{', '.join(sorted(missing))}{C.RESET}")

        if not cross_site_drift:
            print(f"  {C.GREEN}All JS sites consistent (canonical CRM fields){C.RESET}")

    # Check Python implementations
    print(f"\n{C.BOLD}Python Implementations{C.RESET}")
    print("-" * 50)

    if not PY_DATABASES:
        print(f"  {C.DIM}No Python CRM databases configured yet{C.RESET}")
        print(f"  {C.DIM}Add database paths to PY_DATABASES in this script as sites are built{C.RESET}")
    else:
        for site_name, db_path in PY_DATABASES.items():
            print(f"\n{C.BLUE}{site_name}{C.RESET} ({db_path.name})")

            if not db_path.exists():
                print(f"  {C.RED}Database not found{C.RESET}")
                has_missing = True
                continue

            all_ok = True
            for table_name, info in canonical.items():
                py_fields = info["py_fields"]
                sqlite_table = CRM_TABLES[table_name]
                actual = parse_sqlite_table(db_path, sqlite_table)

                if actual is None:
                    print(f"  {C.YELLOW}{table_name} ({sqlite_table}){C.RESET}: table not found")
                    has_missing = True
                    continue

                result = compare_fields(py_fields, actual, f"{site_name}/{table_name}", is_python=True)

                if result["status"] == "ok":
                    if verbose:
                        print(f"  {C.GREEN}{table_name}{C.RESET}: {len(py_fields)} fields - OK")
                elif result["status"] == "drift":
                    all_ok = False
                    has_drift = True
                    print(f"  {C.RED}{table_name}{C.RESET}: DRIFT DETECTED")
                    if result["missing"]:
                        print(f"    Missing: {C.RED}{', '.join(result['missing'])}{C.RESET}")
                    if result["extra"]:
                        print(f"    Extra: {C.YELLOW}{', '.join(result['extra'])}{C.RESET}")

            if all_ok and not verbose:
                print(f"  {C.GREEN}All tables in sync{C.RESET}")

    # Summary
    print(f"\n{'=' * 50}")
    if has_drift:
        print(f"{C.RED}{C.BOLD}DRIFT DETECTED{C.RESET} - schemas are out of sync")
        print(f"Update the canonical schema at: {CANONICAL_SCHEMA}")
        print(f"Then update the implementations to match.")
        sys.exit(1)
    elif has_missing:
        print(f"{C.YELLOW}{C.BOLD}INCOMPLETE{C.RESET} - some implementations are missing")
        print(f"Python CRM module has not been built yet.")
        sys.exit(2)
    else:
        print(f"{C.GREEN}{C.BOLD}ALL IN SYNC{C.RESET} - all implementations match the canonical schema")
        sys.exit(0)


if __name__ == "__main__":
    main()
