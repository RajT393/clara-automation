"""
diff_generator.py
Generates a structured changelog between v1 and v2 account memos.
Produces both changes.json and changes.md
"""

import json
from datetime import datetime
from typing import Any


def deep_diff(v1: Any, v2: Any, path: str = "") -> list:
    """
    Recursively find differences between two objects.
    Returns list of change records.
    """
    changes = []

    # Skip internal metadata fields
    skip_fields = {"_extraction_method", "extracted_at", "source_file", "call_type"}
    if path.split(".")[-1] in skip_fields:
        return changes

    if isinstance(v1, dict) and isinstance(v2, dict):
        all_keys = set(v1.keys()) | set(v2.keys())
        for key in sorted(all_keys):
            if key in skip_fields:
                continue
            child_path = f"{path}.{key}" if path else key
            if key not in v1:
                changes.append({
                    "field": child_path,
                    "change_type": "added",
                    "v1_value": None,
                    "v2_value": v2[key],
                    "note": "New field added in onboarding"
                })
            elif key not in v2:
                changes.append({
                    "field": child_path,
                    "change_type": "removed",
                    "v1_value": v1[key],
                    "v2_value": None,
                    "note": "Field removed in onboarding"
                })
            else:
                child_changes = deep_diff(v1[key], v2[key], child_path)
                changes.extend(child_changes)

    elif isinstance(v1, list) and isinstance(v2, list):
        if sorted(str(x) for x in v1) != sorted(str(x) for x in v2):
            added = [x for x in v2 if x not in v1]
            removed = [x for x in v1 if x not in v2]
            if added or removed:
                changes.append({
                    "field": path,
                    "change_type": "list_updated",
                    "v1_value": v1,
                    "v2_value": v2,
                    "added_items": added,
                    "removed_items": removed,
                    "note": "List updated in onboarding"
                })
    else:
        if v1 != v2:
            # Determine significance
            significance = "minor"
            critical_fields = [
                "emergency_routing_rules", "business_hours", "call_transfer_rules",
                "integration_constraints", "emergency_definition"
            ]
            for cf in critical_fields:
                if cf in path:
                    significance = "critical"
                    break

            changes.append({
                "field": path,
                "change_type": "updated",
                "v1_value": v1,
                "v2_value": v2,
                "significance": significance,
                "note": f"Confirmed in onboarding call — overrides demo assumption" if v1 is None else "Updated with precise onboarding data"
            })

    return changes


def generate_changelog(v1_memo: dict, v2_memo: dict, account_id: str) -> dict:
    """Generate structured changelog between v1 and v2 memos."""
    changes = deep_diff(v1_memo, v2_memo)

    critical = [c for c in changes if c.get("significance") == "critical" or c.get("change_type") == "list_updated"]
    minor = [c for c in changes if c not in critical]

    summary = {
        "account_id": account_id,
        "company_name": v2_memo.get("company_name"),
        "changelog_generated_at": datetime.utcnow().isoformat() + "Z",
        "v1_source": "demo_call",
        "v2_source": "onboarding_call",
        "total_changes": len(changes),
        "critical_changes": len(critical),
        "minor_changes": len(minor),
        "changes": {
            "critical": critical,
            "minor": minor
        }
    }
    return summary


def generate_markdown_changelog(changelog: dict) -> str:
    """Generate human-readable markdown changelog."""
    lines = []
    lines.append(f"# Changelog — {changelog.get('company_name', 'Unknown')}")
    lines.append(f"**Account ID:** {changelog.get('account_id')}")
    lines.append(f"**Generated:** {changelog.get('changelog_generated_at')}")
    lines.append(f"**Total Changes:** {changelog.get('total_changes')}")
    lines.append("")

    lines.append("## Summary")
    lines.append(f"- {changelog.get('critical_changes')} critical changes (routing, hours, emergency logic)")
    lines.append(f"- {changelog.get('minor_changes')} minor changes (notes, addresses, labels)")
    lines.append("")

    critical = changelog.get("changes", {}).get("critical", [])
    if critical:
        lines.append("## 🔴 Critical Changes")
        lines.append("_These affect call routing, emergency handling, or integration constraints._")
        lines.append("")
        for c in critical:
            lines.append(f"### `{c['field']}`")
            lines.append(f"- **Change type:** {c['change_type']}")
            if c.get("v1_value") is not None:
                lines.append(f"- **Was (v1):** `{json.dumps(c['v1_value'])}`")
            if c.get("v2_value") is not None:
                lines.append(f"- **Now (v2):** `{json.dumps(c['v2_value'])}`")
            if c.get("added_items"):
                lines.append(f"- **Added:** {c['added_items']}")
            if c.get("removed_items"):
                lines.append(f"- **Removed:** {c['removed_items']}")
            lines.append(f"- **Note:** {c.get('note', '')}")
            lines.append("")

    minor = changelog.get("changes", {}).get("minor", [])
    if minor:
        lines.append("## 🟡 Minor Changes")
        lines.append("")
        for c in minor:
            v1_str = json.dumps(c.get('v1_value')) if c.get('v1_value') is not None else "_null_"
            v2_str = json.dumps(c.get('v2_value')) if c.get('v2_value') is not None else "_null_"
            lines.append(f"- **`{c['field']}`**: {v1_str} → {v2_str} _{c.get('note', '')}_")

    lines.append("")
    lines.append("---")
    lines.append("_Generated by Clara Automation Pipeline B_")

    return "\n".join(lines)
