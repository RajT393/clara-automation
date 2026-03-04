"""
test_n8n.py
Tests the n8n webhook endpoints and the Python pipeline directly.
Run: python test_n8n.py
"""

import json
import sys
import os
import requests
from datetime import datetime

N8N_BASE = "http://localhost:5678"

# Test transcripts - different edge cases
TEST_CASES = [
    {
        "name": "Normal electrical company",
        "account_id": "ACC_TEST_ELECTRICAL",
        "demo_transcript": """
Client: We are ABC Electrical Solutions based in Houston Texas.
We do commercial and residential electrical work, panel upgrades, generator installs.
Business hours Monday to Friday 8am to 5pm Central time.
Emergency contact is John Martinez at 713-555-0100.
We use ServiceTrade but please never create jobs automatically.
After hours only real emergencies like live wires or power outages get routed to John.
        """,
        "onboarding_transcript": """
Confirmed company name: ABC Electrical Solutions LLC.
Exact hours: 8:30 AM to 5:30 PM Central Time Monday through Friday.
Emergency triggers confirmed: live exposed wire, complete power outage in commercial building,
electrical fire or burning smell, generator failure at critical facility.
Transfer timeout: 45 seconds then fallback message.
Office address: 4500 Main Street Suite 200 Houston Texas 77002.
Fallback message: Our emergency team has been notified and will call you back within 20 minutes.
ServiceTrade constraint confirmed: never create any job automatically.
        """
    },
    {
        "name": "Missing data edge case",
        "account_id": "ACC_TEST_MISSING",
        "demo_transcript": """
Client: Hi we are interested in Clara for our business.
We do fire protection work. 
We get a lot of calls and need help managing them.
        """,
        "onboarding_transcript": """
Company: Reliable Fire Protection Inc.
Hours: Monday to Friday 7am to 4pm Mountain Time.
Emergency: active sprinkler discharge, fire alarm triggered, suppression system failure.
Contact: dispatch at 303-555-0177.
        """
    },
    {
        "name": "Complex after-hours routing",
        "account_id": "ACC_TEST_COMPLEX",
        "demo_transcript": """
Client: We are Metro HVAC Services in Chicago Illinois.
Commercial HVAC, refrigeration systems, industrial cooling.
Office hours Monday to Friday 7 to 5 Central.
After hours we have two on-call techs who rotate weekly.
Emergencies are refrigeration failures at food facilities and complete HVAC loss in winter.
        """,
        "onboarding_transcript": """
Metro HVAC Services confirmed.
Hours: Monday to Friday 7:00 AM to 5:00 PM Central Time.
Emergency routing: Primary on-call 312-555-0155, Secondary 312-555-0166.
Timeout: 30 seconds each.
Refrigeration failure at food service: Tier 1 emergency, immediate page.
HVAC loss in winter below 32F outside: Tier 1 emergency.
Non-emergency after hours: message and next business day callback.
No software integrations currently.
Address: 1200 West Lake Street Chicago Illinois 60607.
        """
    }
]


def test_python_pipeline(test_case):
    """Test using Python scripts directly (most reliable)."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
    from pipeline_a import run_pipeline_a
    from pipeline_b import run_pipeline_b

    # Write temp transcript files
    demo_path = f"data/demo/test_{test_case['account_id']}.txt"
    onboard_path = f"data/onboarding/test_{test_case['account_id']}.txt"

    os.makedirs("data/demo", exist_ok=True)
    os.makedirs("data/onboarding", exist_ok=True)

    with open(demo_path, "w") as f:
        f.write(test_case["demo_transcript"])
    with open(onboard_path, "w") as f:
        f.write(test_case["onboarding_transcript"])

    print(f"\n{'='*55}")
    print(f"TEST: {test_case['name']}")
    print(f"{'='*55}")

    # Pipeline A
    result_a = run_pipeline_a(demo_path, account_id=test_case["account_id"])
    print(f"Pipeline A: {result_a.get('status')} | Method: {result_a.get('extraction_method')}")
    print(f"Questions: {result_a.get('questions_count', 0)} open")

    # Pipeline B
    result_b = run_pipeline_b(onboard_path, account_id=test_case["account_id"])
    print(f"Pipeline B: {result_b.get('status')} | Changes: {result_b.get('change_count', 0)}")

    return result_a.get('status') == 'success' and result_b.get('status') == 'success'


def test_n8n_webhook(test_case):
    """Test via n8n webhook."""
    print(f"\n[n8n] Testing: {test_case['name']}")
    try:
        # Pipeline A webhook
        r = requests.post(
            f"{N8N_BASE}/webhook-test/pipeline-a",
            json={
                "transcript": test_case["demo_transcript"],
                "account_id": test_case["account_id"] + "_N8N"
            },
            timeout=30
        )
        print(f"[n8n] Pipeline A: HTTP {r.status_code}")
        if r.status_code == 200:
            print(f"[n8n] Response: {r.text[:200]}")
            return True
    except Exception as e:
        print(f"[n8n] Webhook not available: {e}")
        print("[n8n] This is OK - workflow needs to be activated in n8n UI first")
    return False


def run_all_tests():
    print("\n" + "="*55)
    print("  CLARA AUTOMATION PIPELINE - TEST SUITE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*55)

    results = []

    print("\n--- PYTHON PIPELINE TESTS ---")
    for tc in TEST_CASES:
        passed = test_python_pipeline(tc)
        results.append({"test": tc["name"], "method": "python", "passed": passed})

    print("\n--- N8N WEBHOOK TESTS ---")
    for tc in TEST_CASES[:1]:  # just test first one via n8n
        passed = test_n8n_webhook(tc)
        results.append({"test": tc["name"], "method": "n8n", "passed": passed})

    print(f"\n{'='*55}")
    print("TEST RESULTS SUMMARY")
    print(f"{'='*55}")
    for r in results:
        status = "✓ PASS" if r["passed"] else "✗ FAIL"
        print(f"  {status} | [{r['method']}] {r['test']}")

    passed = sum(1 for r in results if r["passed"])
    print(f"\n  Total: {passed}/{len(results)} passed")
    print(f"{'='*55}\n")

    # Save test report
    with open("outputs/test_report.json", "w") as f:
        json.dump({
            "run_at": datetime.now().isoformat(),
            "results": results,
            "passed": passed,
            "total": len(results)
        }, f, indent=2)
    print("Test report saved: outputs/test_report.json")


if __name__ == "__main__":
    run_all_tests()