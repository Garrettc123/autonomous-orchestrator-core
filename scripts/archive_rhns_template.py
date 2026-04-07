#!/usr/bin/env python3
"""
RHNS Template Archiver
======================
Archives a completed client engagement as a parameterized RHNS template
in the Notion "RHNS Template Library" database.

Triggered by GitHub Actions workflow_dispatch or repository_dispatch.
Accepts engagement data as JSON via --data flag or ENGAGEMENT_DATA env var.

Usage:
    python archive_rhns_template.py --data '{"template_name": "...", ...}'
    ENGAGEMENT_DATA='{"template_name": "..."}' python archive_rhns_template.py
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone


# ── Configuration ──────────────────────────────────────────────────────────────

NOTION_API_VERSION = "2022-06-28"
NOTION_DATABASE_ID = "c0d0b2c034314f1f87b1f92ddecb8f8d"

# Valid enum values for select/multi-select properties
VALID_VERTICALS = [
    "General Contractor", "Utility", "Healthcare", "Energy",
    "Manufacturing", "Engineering Services", "Construction", "Other"
]
VALID_REVENUE_RANGES = ["$0-1M", "$1-5M", "$5-10M", "$10-50M", "$50M+"]
VALID_CLIENT_TYPES = ["SMB", "Mid-Market", "Enterprise", "Government"]
VALID_PRODUCTS = [
    "Starter Audit", "MAUT Engine", "Revenue Recovery Sprint",
    "AI Growth Engine", "Platform License"
]
VALID_STATUSES = ["Draft", "Active Template", "Archived"]
VALID_TAGS = [
    "revenue-leak", "lead-gen", "churn-reduction", "seo",
    "pricing", "automation", "ai-deployment", "data-ops"
]


# ── Engagement Data Schema ─────────────────────────────────────────────────────

REQUIRED_FIELDS = ["template_name"]
OPTIONAL_FIELDS = {
    "vertical": None,
    "revenue_range": None,
    "client_type": None,
    "product_used": None,
    "status": "Active Template",
    "engagement_id": None,
    "outcome_summary": None,
    "tags": [],
    # RHNS layers — the core template content
    "reason": "",
    "harmony": "",
    "navigation": "",
    "standards": "",
    # Optional metadata
    "client_name": None,
    "engagement_date": None,
    "parameters": {},  # Key-value pairs for templatization
}


# ── Notion API helpers ─────────────────────────────────────────────────────────

def notion_request(endpoint: str, method: str = "POST", body: dict = None) -> dict:
    """Make a request to the Notion API."""
    token = os.environ.get("NOTION_API_KEY")
    if not token:
        print("ERROR: NOTION_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    url = f"https://api.notion.com/v1/{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"ERROR: Notion API returned {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


def build_rich_text(text: str) -> list:
    """Build a Notion rich_text array from a plain string."""
    if not text:
        return []
    # Notion rich_text blocks are limited to 2000 chars each
    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks]


def build_select(value: str, valid_options: list) -> dict | None:
    """Build a Notion select property, validating against allowed values."""
    if not value:
        return None
    if value not in valid_options:
        print(f"WARNING: '{value}' not in {valid_options}. Skipping.", file=sys.stderr)
        return None
    return {"select": {"name": value}}


def build_multi_select(values: list, valid_options: list) -> dict | None:
    """Build a Notion multi_select property."""
    if not values:
        return None
    validated = [v for v in values if v in valid_options]
    if len(validated) != len(values):
        skipped = set(values) - set(validated)
        print(f"WARNING: Skipping invalid tags: {skipped}", file=sys.stderr)
    if not validated:
        return None
    return {"multi_select": [{"name": v} for v in validated]}


# ── Template Content Builder ───────────────────────────────────────────────────

def build_rhns_content(data: dict) -> list:
    """
    Build Notion block children representing the RHNS template content.
    Each RHNS layer gets a heading + its content as paragraphs.
    Parameters section is appended for templatization.
    """
    blocks = []

    # Header block
    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": "🧬"},
            "rich_text": build_rich_text(
                "RHNS Parameterized Template — Auto-archived from completed engagement. "
                "Clone this template and replace {{parameters}} for new clients."
            ),
            "color": "blue_background",
        }
    })

    blocks.append({"object": "block", "type": "divider", "divider": {}})

    # ── RHNS Layers ──
    layers = [
        ("🔍 Reason", data.get("reason", ""),
         "First-principles analysis: what is the actual objective, leverage point, and real blocker?"),
        ("⚖️ Harmony", data.get("harmony", ""),
         "System alignment: how do marketing, ops, sales, and delivery interact or conflict?"),
        ("🧭 Navigation", data.get("navigation", ""),
         "Execution routing: what path, tools, and sequence produce the outcome?"),
        ("📏 Standards", data.get("standards", ""),
         "Quality guardrails: what quality bars, metrics, and discipline prevent drift?"),
    ]

    for heading, content, description in layers:
        # H2 heading
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": build_rich_text(heading), "color": "default"}
        })
        # Description in gray italic
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": description},
                    "annotations": {"italic": True, "color": "gray"}
                }]
            }
        })
        # Actual content
        if content:
            # Split into paragraphs
            for para in content.split("\n\n"):
                para = para.strip()
                if para:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": build_rich_text(para)}
                    })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": "{{TO BE FILLED — clone and customize}}"},
                        "annotations": {"italic": True, "color": "orange"}
                    }]
                }
            })

        blocks.append({"object": "block", "type": "divider", "divider": {}})

    # ── Parameters Section ──
    parameters = data.get("parameters", {})
    if parameters:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": build_rich_text("🔧 Template Parameters"), "color": "default"}
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "Replace these values when cloning for a new engagement:"},
                    "annotations": {"italic": True, "color": "gray"}
                }]
            }
        })

        # Parameter table as bulleted list
        for key, value in parameters.items():
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": f"{{{{{key}}}}}"}, "annotations": {"bold": True, "code": True}},
                        {"type": "text", "text": {"content": f" → {value}"}},
                    ]
                }
            })

    # ── Outcome Section ──
    outcome = data.get("outcome_summary")
    if outcome:
        blocks.append({"object": "block", "type": "divider", "divider": {}})
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {"rich_text": build_rich_text("📊 Original Engagement Outcome"), "color": "default"}
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": build_rich_text(outcome)}
        })

    return blocks


# ── Main Archiver ──────────────────────────────────────────────────────────────

def archive_engagement(data: dict) -> dict:
    """Archive a completed engagement as an RHNS template in Notion."""

    # Validate required fields
    for field in REQUIRED_FIELDS:
        if field not in data or not data[field]:
            print(f"ERROR: Required field '{field}' is missing.", file=sys.stderr)
            sys.exit(1)

    # Apply defaults for optional fields
    for field, default in OPTIONAL_FIELDS.items():
        if field not in data:
            data[field] = default

    # Build properties
    properties = {
        "Template Name": {
            "title": build_rich_text(data["template_name"])
        },
    }

    # Select properties
    select_mappings = [
        ("Vertical", data.get("vertical"), VALID_VERTICALS),
        ("Revenue Range", data.get("revenue_range"), VALID_REVENUE_RANGES),
        ("Client Type", data.get("client_type"), VALID_CLIENT_TYPES),
        ("Product Used", data.get("product_used"), VALID_PRODUCTS),
        ("Status", data.get("status"), VALID_STATUSES),
    ]

    for prop_name, value, options in select_mappings:
        result = build_select(value, options)
        if result:
            properties[prop_name] = result

    # Rich text properties
    if data.get("engagement_id"):
        properties["Engagement ID"] = {"rich_text": build_rich_text(data["engagement_id"])}
    if data.get("outcome_summary"):
        properties["Outcome Summary"] = {"rich_text": build_rich_text(data["outcome_summary"])}

    # Multi-select (tags)
    tags_result = build_multi_select(data.get("tags", []), VALID_TAGS)
    if tags_result:
        properties["Template Tags"] = tags_result

    # Number (reuse count starts at 0)
    properties["Reuse Count"] = {"number": 0}

    # Date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    properties["Created"] = {"date": {"start": today}}

    # Build page content (RHNS template body)
    children = build_rhns_content(data)

    # Create the page in Notion
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "icon": {"type": "emoji", "emoji": "🧬"},
        "properties": properties,
        "children": children,
    }

    print(f"Creating RHNS template: {data['template_name']}...")
    result = notion_request("pages", method="POST", body=payload)

    page_url = result.get("url", "")
    page_id = result.get("id", "")
    print(f"SUCCESS: Template created")
    print(f"  Page ID:  {page_id}")
    print(f"  URL:      {page_url}")

    return {"page_id": page_id, "url": page_url, "template_name": data["template_name"]}


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Archive engagement as RHNS template in Notion")
    parser.add_argument("--data", type=str, help="JSON string of engagement data")
    parser.add_argument("--file", type=str, help="Path to JSON file with engagement data")
    args = parser.parse_args()

    # Load engagement data from flag, file, or env
    raw = None
    if args.data:
        raw = args.data
    elif args.file:
        with open(args.file) as f:
            raw = f.read()
    elif os.environ.get("ENGAGEMENT_DATA"):
        raw = os.environ["ENGAGEMENT_DATA"]
    else:
        print("ERROR: Provide engagement data via --data, --file, or ENGAGEMENT_DATA env var.", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    result = archive_engagement(data)

    # Output result for GitHub Actions
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"page_id={result['page_id']}\n")
            f.write(f"page_url={result['url']}\n")
            f.write(f"template_name={result['template_name']}\n")

    # Also write JSON result to stdout for piping
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
