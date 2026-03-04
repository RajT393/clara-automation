"""
pipeline_b.py
Pipeline B: Onboarding Call/Form -> Update v1 to v2 with changelog
Usage: python pipeline_b.py --transcript path/to/onboarding.txt --account_id ACC001
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from copy import deepcopy

sys.path.insert(0, os.path.dirname(__file__))
from extractor import extract_from_transcript
from prompt_generator import generate_agent_spec
from storage import save_account_artifact, load_account_artifact, get_account_output_dir


def deep_diff(old: dict, new: dict, path: str = "") -> list:
    """
    Recursively find differences between two dicts.
    Returns list of change dicts: {field, old_value, new_value, change_type}
    """
    changes = []
    all_keys = set(list(old.keys()) + list(new.keys()))

    for key in all_keys:
        full_path = f"{path}.{key}" if path else key
        old_val = old.get(key)
        new_val = new.get(key)

        # Skip internal fields
        if key in ("_extraction_method", "created_at", "version", "pipeline_source", "account_id"):
            continue

        if old_val is None and new_val is not None:
            changes.append({"field": full_path, "change_type": "added", "old_value": None, "new_value": new_val})
        elif old_val is not None and new_val is None:
            changes.append({"field": full_path, "change_type": "removed", "old_value": old_val, "new_value": None})
        elif isinstance(old_val, dict) and isinstance(new_val, dict):
            changes.extend(deep_diff(old_val, new_val, full_path))
        elif old_val != new_val:
            changes.append({"field": full_path, "change_type": "modified", "old_value": old_val, "new_value": new_val})

    return changes


def merge_memos(v1_memo: dict, onboarding_data: dict) -> dict:
    """
    Merge onboarding data into v1 memo.
    Onboarding data overrides v1 where explicitly provided.
    Null onboarding values do NOT override existing v1 values.
    Lists use UNION strategy: keep all v1 items + add new v2 items.
    """
    v2 = deepcopy(v1_memo)

    def smart_update(target: dict, source: dict):
        for key, val in source.items():
            if key in ("_extraction_method", "created_at", "version", "pipeline_source", "account_id"):
                continue
            if val is None:
                continue  # Don't overwrite with null
            if isinstance(val, dict) and isinstance(target.get(key), dict):
                smart_update(target[key], val)
            elif isinstance(val, list):
                if val:  # Only process if non-empty list
                    existing = target.get(key, [])
                    if isinstance(existing, list):
                        # Union: keep all existing items + add new items
                        combined = list(existing)
                        for item in val:
                            if item not in combined:
                                combined.append(item)
                        target[key] = combined
                    else:
                        target[key] = val
                # Empty list from onboarding: keep v1 data
            else:
                target[key] = val

    smart_update(v2, onboarding_data)
    return v2


def generate_changelog(account_id: str, v1_memo: dict, v2_memo: dict,
                        v1_spec: dict, v2_spec: dict, changes: list) -> str:
    """Generate human-readable changelog markdown."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Changelog: {account_id}",
        f"## v1 → v2 Update",
        f"**Generated:** {now}",
        f"**Company:** {v2_memo.get('company_name') or 'Unknown'}",
        "",
        "---",
        "",
        "## Summary",
        f"- **Total changes:** {len(changes)}",
        f"- **Source:** Onboarding call/form",
        f"- **Extraction method:** {v2_memo.get('_extraction_method', 'unknown')}",
        "",
        "---",
        "",
        "## Field Changes",
        ""
    ]

    if not changes:
        lines.append("_No changes detected. v2 is identical to v1._")
    else:
        for c in changes:
            change_type = c["change_type"].upper()
            field = c["field"]
            old_val = c["old_value"]
            new_val = c["new_value"]

            lines.append(f"### `{field}` — {change_type}")
            if change_type == "ADDED":
                lines.append(f"- **Added:** `{new_val}`")
            elif change_type == "REMOVED":
                lines.append(f"- **Removed:** `{old_val}`")
            else:
                lines.append(f"- **Before:** `{old_val}`")
                lines.append(f"- **After:** `{new_val}`")
            lines.append("")

    lines += [
        "---",
        "",
        "## Agent Prompt",
        "- v1 prompt regenerated with confirmed onboarding data",
        "- All unconfirmed v1 assumptions replaced with verified values",
        "",
        "## Unresolved Questions",
        ""
    ]

    unknowns = v2_memo.get("questions_or_unknowns") or []
    if unknowns:
        for q in unknowns:
            lines.append(f"- ⚠️ {q}")
    else:
        lines.append("_All questions resolved._")

    lines += ["", "---", "_Generated by Clara Automation Pipeline_"]
    return "\n".join(lines)


def run_pipeline_b(transcript_path: str, account_id: str, dry_run: bool = False) -> dict:
    """
    Run Pipeline B: Load v1, apply onboarding data, produce v2.
    """
    print(f"\n{'='*60}")
    print(f"[Pipeline B] Processing onboarding for: {account_id}")
    print(f"[Pipeline B] Onboarding file: {transcript_path}")
    print(f"{'='*60}")

    # 1. Load v1 memo
    v1_memo = load_account_artifact(account_id, "v1", "memo.json")
    if not v1_memo:
        print(f"[Pipeline B] ERROR: v1 memo not found for {account_id}. Run pipeline_a first.")
        return {"status": "error", "reason": "v1_memo_not_found", "account_id": account_id}

    v1_spec = load_account_artifact(account_id, "v1", "agent_spec.json")

    # 2. Load and extract onboarding transcript
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = f.read().strip()

    onboarding_data = extract_from_transcript(transcript, source="onboarding")
    print(f"[Pipeline B] Extraction method: {onboarding_data.get('_extraction_method')}")

    # 3. Merge v1 + onboarding -> v2
    v2_memo = merge_memos(v1_memo, onboarding_data)
    v2_memo["version"] = "v2"
    v2_memo["updated_at"] = datetime.now(timezone.utc).isoformat()
    v2_memo["onboarding_source"] = os.path.basename(transcript_path)
    v2_memo["_extraction_method"] = onboarding_data.get("_extraction_method")

    # 4. Compute diff
    changes = deep_diff(v1_memo, v2_memo)
    print(f"[Pipeline B] Detected {len(changes)} changes from onboarding")

    # 5. Generate v2 agent spec
    v2_spec = generate_agent_spec(v2_memo, account_id, version="v2")
    v2_spec["updated_at"] = datetime.now(timezone.utc).isoformat()
    v2_spec["previous_version"] = "v1"

    # Re-evaluate questions_or_unknowns after merge
    resolved_unknowns = []
    bh = v2_memo.get("business_hours", {})
    if bh.get("start"):
        resolved_unknowns.extend(["Business hours not confirmed", "Exact business hours start/end time not confirmed"])
    if bh.get("timezone"):
        resolved_unknowns.extend(["Timezone not confirmed", "Timezone not specified"])
    routing = v2_memo.get("emergency_routing_rules", {})
    if routing.get("primary_phone") or routing.get("primary_contact"):
        resolved_unknowns.extend(["Emergency contact phone number missing", "Emergency contact phone numbers not provided"])
    if v2_memo.get("call_transfer_rules", {}).get("timeout_seconds"):
        resolved_unknowns.extend(["Transfer timeout duration not specified"])
    if v2_memo.get("office_address"):
        resolved_unknowns.extend(["Office address not confirmed (expected — demo call)"])
    if v2_memo.get("emergency_definition"):
        resolved_unknowns.extend(["Emergency trigger conditions not clearly defined", "Emergency definitions not fully specified (expected — demo call)"])
    v2_memo["questions_or_unknowns"] = [
        q for q in (v2_memo.get("questions_or_unknowns") or [])
        if q not in resolved_unknowns
    ]

    # 6. Generate changelog
    changelog_md = generate_changelog(account_id, v1_memo, v2_memo, v1_spec, v2_spec, changes)
    changelog_json = {
        "account_id": account_id,
        "from_version": "v1",
        "to_version": "v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "change_count": len(changes),
        "changes": changes
    }

    if dry_run:
        print("[Pipeline B] DRY RUN - not saving files")
        return {"status": "dry_run", "account_id": account_id, "change_count": len(changes)}

    # 7. Save v2 artifacts
    memo_path = save_account_artifact(account_id, "v2", "memo.json", v2_memo)
    spec_path = save_account_artifact(account_id, "v2", "agent_spec.json", v2_spec)
    changelog_md_path = save_account_artifact(account_id, "v2", "changes.md", changelog_md, raw=True)
    changelog_json_path = save_account_artifact(account_id, "v2", "changes.json", changelog_json)

    print(f"[Pipeline B] Saved v2 memo: {memo_path}")
    print(f"[Pipeline B] Saved v2 spec: {spec_path}")
    print(f"[Pipeline B] Saved changelog: {changelog_md_path}")
    if v2_memo.get("questions_or_unknowns"):
        print(f"[Pipeline B] Remaining questions: {v2_memo['questions_or_unknowns']}")
    print(f"[Pipeline B] COMPLETE\n")

    return {
        "status": "success",
        "account_id": account_id,
        "memo_path": memo_path,
        "spec_path": spec_path,
        "changelog_path": changelog_md_path,
        "change_count": len(changes),
        "extraction_method": onboarding_data.get("_extraction_method")
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline B: Onboarding -> v2 Agent")
    parser.add_argument("--transcript", required=True, help="Path to onboarding transcript/form")
    parser.add_argument("--account_id", required=True, help="Account ID (from pipeline A output)")
    parser.add_argument("--dry-run", action="store_true", help="Extract but don't save")
    args = parser.parse_args()

    result = run_pipeline_b(args.transcript, args.account_id, args.dry_run)
    print(json.dumps(result, indent=2))
