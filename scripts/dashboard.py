"""
dashboard.py
Simple CLI dashboard showing all processed accounts and their status.
Usage: python dashboard.py
       python dashboard.py --account_id ACC001
       python dashboard.py --diff ACC001
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from storage import get_account_summary, load_account_artifact, list_all_accounts


def print_dashboard():
    """Print overview of all accounts."""
    accounts = get_account_summary()
    if not accounts:
        print("No accounts processed yet. Run batch_run.py first.")
        return

    print(f"\n{'='*70}")
    print(f"  CLARA AUTOMATION PIPELINE - Account Dashboard")
    print(f"{'='*70}")
    print(f"  {'ACCOUNT ID':<25} {'COMPANY':<25} {'STATUS':<12} {'QUESTIONS'}")
    print(f"  {'-'*65}")

    for acc in accounts:
        status = "v1 + v2 ✓" if acc["has_v2"] else "v1 only →"
        q = f"{acc['open_questions']} open" if acc["open_questions"] else "none"
        print(f"  {acc['account_id']:<25} {acc['company_name'][:24]:<25} {status:<12} {q}")

    print(f"{'='*70}")
    print(f"  Total accounts: {len(accounts)} | "
          f"With v2: {sum(1 for a in accounts if a['has_v2'])} | "
          f"v1 only: {sum(1 for a in accounts if not a['has_v2'])}")
    print(f"{'='*70}\n")


def print_account_detail(account_id: str):
    """Print detailed view of a single account."""
    memo = load_account_artifact(account_id, "v2", "memo.json") or \
           load_account_artifact(account_id, "v1", "memo.json")
    if not memo:
        print(f"Account {account_id} not found.")
        return

    version = memo.get("version", "v1")
    print(f"\n{'='*60}")
    print(f"  Account: {account_id} ({version})")
    print(f"  Company: {memo.get('company_name') or 'Unknown'}")
    print(f"{'='*60}")

    bh = memo.get("business_hours") or {}
    print(f"\nBusiness Hours:")
    print(f"  Days: {bh.get('days') or 'Not confirmed'}")
    print(f"  Hours: {bh.get('start') or '?'} - {bh.get('end') or '?'}")
    print(f"  Timezone: {bh.get('timezone') or 'Not confirmed'}")

    print(f"\nServices: {', '.join(memo.get('services_supported') or []) or 'Not listed'}")
    print(f"Address: {memo.get('office_address') or 'Not provided'}")

    routing = memo.get("emergency_routing_rules") or {}
    print(f"\nEmergency Routing:")
    print(f"  Primary: {routing.get('primary_contact') or '?'} | {routing.get('primary_phone') or '?'}")
    print(f"  Fallback: {routing.get('fallback') or 'Not defined'}")

    constraints = memo.get("integration_constraints") or []
    if constraints:
        print(f"\nConstraints:")
        for c in constraints:
            print(f"  - {c}")

    unknowns = memo.get("questions_or_unknowns") or []
    if unknowns:
        print(f"\n⚠ Open Questions ({len(unknowns)}):")
        for q in unknowns:
            print(f"  - {q}")
    else:
        print(f"\n✓ No open questions")

    print()


def print_diff(account_id: str):
    """Print changelog for an account (v1 -> v2 diff)."""
    changelog = load_account_artifact(account_id, "v2", "changes.md")
    if not changelog:
        print(f"No v2 changelog found for {account_id}.")
        return
    print(changelog)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clara Pipeline Dashboard")
    parser.add_argument("--account_id", help="Show detail for specific account")
    parser.add_argument("--diff", help="Show v1->v2 diff for account")
    args = parser.parse_args()

    if args.diff:
        print_diff(args.diff)
    elif args.account_id:
        print_account_detail(args.account_id)
    else:
        print_dashboard()
