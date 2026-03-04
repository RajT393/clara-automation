"""
pipeline_a.py
Pipeline A: Demo Call Transcript -> v1 Account Memo + v1 Agent Spec
Usage: python pipeline_a.py --transcript path/to/transcript.txt --account_id ACC001
"""

import argparse
import json
import os
import sys
import hashlib
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from extractor import extract_from_transcript
from prompt_generator import generate_agent_spec
from storage import save_account_artifact, create_task_tracker_item


def generate_account_id(company_name: str, transcript_path: str) -> str:
    """Generate a stable account ID from company name or file hash."""
    if company_name and company_name != "Unknown Company":
        slug = company_name.lower().replace(" ", "_").replace("&", "and")
        slug = "".join(c for c in slug if c.isalnum() or c == "_")
        return f"ACC_{slug[:20].upper()}"
    # Fallback: hash of filename
    h = hashlib.md5(os.path.basename(transcript_path).encode()).hexdigest()[:6].upper()
    return f"ACC_{h}"


def run_pipeline_a(transcript_path: str, account_id: str = None, dry_run: bool = False) -> dict:
    """
    Run Pipeline A on a single demo call transcript.
    Returns dict with account_id, memo, agent_spec paths.
    """
    print(f"\n{'='*60}")
    print(f"[Pipeline A] Processing: {transcript_path}")
    print(f"{'='*60}")

    # 1. Load transcript
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = f.read().strip()

    if not transcript:
        print("[Pipeline A] ERROR: Empty transcript file")
        return {"status": "error", "reason": "empty_transcript"}

    # 2. Extract structured memo
    memo = extract_from_transcript(transcript, source="demo")

    # 3. Assign account ID
    if not account_id:
        account_id = generate_account_id(
            memo.get("company_name") or "Unknown", transcript_path
        )
    memo["account_id"] = account_id
    memo["pipeline_source"] = "demo_call"
    memo["created_at"] = datetime.now(timezone.utc).isoformat()
    memo["version"] = "v1"

    print(f"[Pipeline A] Account ID: {account_id}")
    print(f"[Pipeline A] Company: {memo.get('company_name') or 'Unknown'}")
    print(f"[Pipeline A] Extraction method: {memo.get('_extraction_method')}")

    # 4. Generate agent spec
    agent_spec = generate_agent_spec(memo, account_id, version="v1")
    agent_spec["created_at"] = datetime.now(timezone.utc).isoformat()

    if dry_run:
        print("[Pipeline A] DRY RUN - not saving files")
        return {"status": "dry_run", "account_id": account_id, "memo": memo, "agent_spec": agent_spec}

    # 5. Save artifacts
    memo_path = save_account_artifact(account_id, "v1", "memo.json", memo)
    spec_path = save_account_artifact(account_id, "v1", "agent_spec.json", agent_spec)

    # 6. Save source transcript reference
    save_account_artifact(account_id, "v1", "source_info.json", {
        "source_file": os.path.basename(transcript_path),
        "source_type": "demo_call",
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "char_count": len(transcript),
        "word_count": len(transcript.split())
    })

    # 7. Create task tracker item
    task = create_task_tracker_item(account_id, memo, version="v1")

    print(f"[Pipeline A] Saved memo: {memo_path}")
    print(f"[Pipeline A] Saved agent spec: {spec_path}")
    if memo.get("questions_or_unknowns"):
        print(f"[Pipeline A] Open questions: {memo['questions_or_unknowns']}")
    print(f"[Pipeline A] COMPLETE\n")

    return {
        "status": "success",
        "account_id": account_id,
        "memo_path": memo_path,
        "spec_path": spec_path,
        "task": task,
        "questions_count": len(memo.get("questions_or_unknowns") or []),
        "extraction_method": memo.get("_extraction_method")
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline A: Demo Call -> v1 Agent")
    parser.add_argument("--transcript", required=True, help="Path to transcript file")
    parser.add_argument("--account_id", help="Optional: override account ID")
    parser.add_argument("--dry-run", action="store_true", help="Extract but don't save")
    args = parser.parse_args()

    result = run_pipeline_a(args.transcript, args.account_id, args.dry_run)
    print(json.dumps(result, indent=2))
