"""
batch_run.py
Batch process all demo + onboarding transcripts in the dataset.
Usage: python batch_run.py --demo_dir data/demo --onboarding_dir data/onboarding
       python batch_run.py --demo_dir data/demo --onboarding_dir data/onboarding --mapping data/mapping.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from pipeline_a import run_pipeline_a
from pipeline_b import run_pipeline_b
from storage import get_account_summary

SUPPORTED_EXTENSIONS = {".txt", ".md", ".json"}


def find_transcript_files(directory: str) -> list:
    """Find all transcript files in a directory."""
    files = []
    if not os.path.exists(directory):
        print(f"[Batch] WARNING: Directory not found: {directory}")
        return files
    for f in sorted(os.listdir(directory)):
        ext = os.path.splitext(f)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            files.append(os.path.join(directory, f))
    return files


def load_mapping(mapping_path: str) -> dict:
    """Load demo->onboarding->account_id mapping file."""
    if mapping_path and os.path.exists(mapping_path):
        with open(mapping_path) as f:
            return json.load(f)
    return {}


def run_batch(demo_dir: str, onboarding_dir: str,
              mapping_path: str = None, dry_run: bool = False) -> dict:
    """
    Run full batch: all demo calls -> Pipeline A, then all onboarding -> Pipeline B.
    Mapping JSON format: [{"demo": "file.txt", "onboarding": "file.txt", "account_id": "ACC001"}]
    """
    start_time = datetime.now(timezone.utc)
    print(f"\n{'='*60}")
    print(f"[Batch] Clara Automation Pipeline - Batch Run")
    print(f"[Batch] Started: {start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    demo_files = find_transcript_files(demo_dir)
    onboarding_files = find_transcript_files(onboarding_dir)
    mapping = load_mapping(mapping_path)

    print(f"[Batch] Found {len(demo_files)} demo files")
    print(f"[Batch] Found {len(onboarding_files)} onboarding files")

    results = {
        "pipeline_a": [],
        "pipeline_b": [],
        "errors": [],
        "summary": {}
    }

    # --- Pipeline A: Demo calls ---
    print(f"\n[Batch] Running Pipeline A ({len(demo_files)} demo calls)...")
    demo_account_map = {}  # filename -> account_id

    for demo_file in demo_files:
        basename = os.path.basename(demo_file)
        # Check if mapping provides an account_id
        account_id = None
        if mapping:
            for entry in mapping:
                if entry.get("demo") == basename:
                    account_id = entry.get("account_id")
                    break

        try:
            result = run_pipeline_a(demo_file, account_id=account_id, dry_run=dry_run)
            results["pipeline_a"].append(result)
            if result.get("status") == "success":
                demo_account_map[basename] = result["account_id"]
                print(f"  ✓ {basename} -> {result['account_id']}")
            else:
                print(f"  ✗ {basename} -> {result.get('reason', 'unknown error')}")
                results["errors"].append({"file": basename, "pipeline": "A", "error": result.get("reason")})
        except Exception as e:
            print(f"  ✗ {basename} -> EXCEPTION: {e}")
            results["errors"].append({"file": basename, "pipeline": "A", "error": str(e)})

    # --- Pipeline B: Onboarding calls ---
    print(f"\n[Batch] Running Pipeline B ({len(onboarding_files)} onboarding calls)...")

    for onboarding_file in onboarding_files:
        basename = os.path.basename(onboarding_file)

        # Try to find matching account_id from mapping or by filename convention
        account_id = None
        if mapping:
            for entry in mapping:
                if entry.get("onboarding") == basename:
                    account_id = entry.get("account_id")
                    break

        # Fallback: match by similar filename (e.g. "acme_demo.txt" -> "acme_onboarding.txt")
        if not account_id:
            stem = os.path.splitext(basename)[0]
            for demo_base, acc_id in demo_account_map.items():
                demo_stem = os.path.splitext(demo_base)[0]
                # Try prefix match
                common = os.path.commonprefix([stem, demo_stem])
                if len(common) >= 3:
                    account_id = acc_id
                    break

        if not account_id:
            print(f"  ? {basename} -> No matching account_id found. Skipping.")
            results["errors"].append({"file": basename, "pipeline": "B", "error": "no_matching_account_id"})
            continue

        try:
            result = run_pipeline_b(onboarding_file, account_id=account_id, dry_run=dry_run)
            results["pipeline_b"].append(result)
            if result.get("status") == "success":
                print(f"  ✓ {basename} -> {account_id} ({result.get('change_count', 0)} changes)")
            else:
                print(f"  ✗ {basename} -> {result.get('reason', 'unknown error')}")
                results["errors"].append({"file": basename, "pipeline": "B", "error": result.get("reason")})
        except Exception as e:
            print(f"  ✗ {basename} -> EXCEPTION: {e}")
            results["errors"].append({"file": basename, "pipeline": "B", "error": str(e)})

    # --- Summary ---
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    a_success = sum(1 for r in results["pipeline_a"] if r.get("status") == "success")
    b_success = sum(1 for r in results["pipeline_b"] if r.get("status") == "success")

    results["summary"] = {
        "run_at": start_time.isoformat(),
        "duration_seconds": round(duration, 2),
        "pipeline_a": {"total": len(demo_files), "success": a_success, "failed": len(demo_files) - a_success},
        "pipeline_b": {"total": len(onboarding_files), "success": b_success, "failed": len(onboarding_files) - b_success},
        "total_errors": len(results["errors"]),
        "accounts_processed": list(demo_account_map.values())
    }

    print(f"\n{'='*60}")
    print(f"[Batch] COMPLETE in {duration:.1f}s")
    print(f"[Batch] Pipeline A: {a_success}/{len(demo_files)} success")
    print(f"[Batch] Pipeline B: {b_success}/{len(onboarding_files)} success")
    print(f"[Batch] Errors: {len(results['errors'])}")
    print(f"{'='*60}\n")

    # Save batch summary
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    summary_path = os.path.join(BASE_DIR, "outputs", f"batch_summary_{start_time.strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[Batch] Summary saved: {summary_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch run Clara Automation Pipeline")
    parser.add_argument("--demo_dir", default="data/demo", help="Directory with demo transcripts")
    parser.add_argument("--onboarding_dir", default="data/onboarding", help="Directory with onboarding transcripts")
    parser.add_argument("--mapping", help="Optional JSON mapping file")
    parser.add_argument("--dry-run", action="store_true", help="Don't save outputs")
    args = parser.parse_args()

    results = run_batch(args.demo_dir, args.onboarding_dir, args.mapping, args.dry_run)
    print("\nFinal account status:")
    for acc in get_account_summary():
        status = "✓ v1+v2" if acc["has_v2"] else "→ v1 only"
        questions = f" ({acc['open_questions']} open questions)" if acc["open_questions"] else ""
        print(f"  {status} | {acc['account_id']} | {acc['company_name']}{questions}")
