"""
generate_sample_outputs.py
Generates complete v1 and v2 outputs for all 5 sample accounts
using the rule-based extractor (no LLM needed — zero cost, fully reproducible).
This script is the "run everything" command for reviewers.
"""

import os
import sys
import json
import re
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from prompt_generator import generate_agent_spec
from diff_generator import generate_changelog, generate_markdown_changelog

BASE_DIR = Path(__file__).parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs" / "accounts"
DEMO_DIR = BASE_DIR / "sample_data" / "demo_transcripts"
ONBOARD_DIR = BASE_DIR / "sample_data" / "onboarding_transcripts"


def smart_extract(transcript: str, call_type: str = "demo") -> dict:
    """
    Enhanced rule-based extraction designed for Clara's transcripts.
    Handles the specific patterns in fire protection / HVAC / electrical call transcripts.
    """
    text = transcript
    text_lower = transcript.lower()

    result = {
        "account_id": None,
        "company_name": None,
        "business_hours": {"days": None, "start": None, "end": None, "timezone": None},
        "office_address": None,
        "services_supported": [],
        "emergency_definition": [],
        "emergency_routing_rules": {
            "primary_contact": None,
            "primary_phone": None,
            "secondary_phone": None,
            "contact_order": [],
            "fallback": None
        },
        "non_emergency_routing_rules": None,
        "call_transfer_rules": {
            "timeout_seconds": None,
            "retries": 1,
            "on_fail_message": None
        },
        "integration_constraints": [],
        "after_hours_flow_summary": None,
        "office_hours_flow_summary": None,
        "questions_or_unknowns": [],
        "notes": None,
        "_extraction_method": "rule_based_enhanced"
    }

    # --- Company name ---
    patterns = [
        r"(?:we'?re|this is|i'?m (?:calling from|with)|company(?:\s+name)? is)\s+([A-Z][A-Za-z\s&]+?)(?:\.|,|\s+and\s|\s+we\s|\s+out\s|\s+based)",
        r"(?:calling|called)\s+([A-Z][A-Za-z\s&]+?)(?:\.|,|\s+and\s)",
        r"Prospect:\s*(?:Sure,?\s+yeah\.?\s+)?(?:We'?re|This is)\s+([A-Z][A-Za-z][A-Za-z\s&]+?)(?:\.|,|\s+We\s|\s+we\s)",
        r"Client \([A-Za-z\s]+\):\s*(?:Yes,?\s+)?(?:We'?re|This is|I'?m with)\s+([A-Z][A-Za-z][A-Za-z\s&]+?)(?:\.|,|\s)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            candidate = m.group(1).strip().rstrip(".,")
            if 3 < len(candidate) < 50:
                result["company_name"] = candidate
                break

    # Fallback: look for capitalized business names in first 500 chars
    if not result["company_name"]:
        m = re.search(r'\b([A-Z][a-z]+ (?:Fire|Alarm|HVAC|Electrical|Protection|Safety|Services?|Systems?|Solutions?)(?:\s+[A-Za-z]+)?)\b', text[:1000])
        if m:
            result["company_name"] = m.group(1)

    # --- Business hours ---
    time_match = re.search(
        r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)\s*(?:to|through|-)\s*(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)',
        text, re.IGNORECASE
    )
    if time_match:
        h1, m1, ap1, h2, m2, ap2 = time_match.groups()
        result["business_hours"]["start"] = f"{h1}:{m1 or '00'} {ap1.upper()}"
        result["business_hours"]["end"] = f"{h2}:{m2 or '00'} {ap2.upper()}"

    # Days
    if re.search(r'monday\s+(?:through|to|-)\s+friday', text_lower):
        result["business_hours"]["days"] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    elif re.search(r'monday\s+(?:through|to|-)\s+saturday', text_lower):
        result["business_hours"]["days"] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    # Timezone
    tz_map = {
        "eastern": "Eastern", "est": "Eastern", "edt": "Eastern",
        "central": "Central", "cst": "Central", "cdt": "Central",
        "mountain": "Mountain", "mst": "Mountain", "mdt": "Mountain",
        "pacific": "Pacific", "pst": "Pacific", "pdt": "Pacific"
    }
    for abbr, full in tz_map.items():
        if re.search(r'\b' + abbr + r'\b', text_lower):
            result["business_hours"]["timezone"] = full + " Time"
            break

    # --- Office address ---
    addr_patterns = [
        # Full address with zip: 4820 Morse Road, Columbus, Ohio 43230
        r'\d{3,5}\s+[A-Z][A-Za-z\s]+(?:Road|Rd|Street|St|Avenue|Ave|Blvd|Boulevard|Drive|Dr|Way|Lane|Ln|Parkway|Pkwy|Industrial)[,\s]+[A-Za-z\s]+,\s*(?:[A-Z]{2}|[A-Za-z]+)\s+\d{5}',
        # Address with state name instead of abbreviation
        r'\d{3,5}\s+[A-Z][A-Za-z\s]+(?:Road|Rd|Street|St|Avenue|Ave|Blvd|Boulevard|Drive|Dr|Way|Lane|Ln|Parkway|Pkwy|Industrial)[,\s]+[A-Za-z\s]+,\s*[A-Za-z]+\s+\d{5}',
        # Simple address: 4820 Morse Road, Columbus, Ohio
        r'\d{3,5}\s+[A-Z][A-Za-z\s]+(?:Road|Rd|Street|St|Avenue|Ave|Blvd|Boulevard|Drive|Dr|Way|Lane|Ln|Parkway|Pkwy|Industrial|Suite\s+\d+)[,\s]+[A-Za-z\s]+,\s*(?:[A-Z]{2}|[A-Za-z]+)(?:\s+\d{5})?',
    ]
    for addr_pat in addr_patterns:
        addr_match = re.search(addr_pat, text)
        if addr_match:
            result["office_address"] = addr_match.group(0).strip().rstrip(",")
            break

    # --- Services ---
    service_map = {
        "fire suppression": "Fire Suppression Systems",
        "sprinkler": "Sprinkler Systems",
        "fire alarm": "Fire Alarm Systems",
        "alarm monitoring": "Alarm Monitoring",
        "fire extinguisher": "Fire Extinguisher Service",
        "hood suppression": "Hood Suppression Systems",
        "hvac": "HVAC Services",
        "electrical": "Electrical Services",
        "panel": "Panel Services",
        "access control": "Access Control",
        "inspection": "Inspections",
        "maintenance": "Maintenance Contracts"
    }
    result["services_supported"] = list({
        v for k, v in service_map.items() if k in text_lower
    })

    # --- Emergency definitions ---
    emergency_map = {
        "sprinkler.*(?:discharge|went off|going off|activated)": "Active sprinkler discharge",
        "fire alarm.*(?:going off|triggered|activated|activation)": "Fire alarm activation",
        "active fire": "Active fire on site",
        "smoke detect": "Smoke detection alarm",
        "suppression.*activ": "Suppression system activation",
        "system failure": "System failure",
        "panel.*(?:failure|offline|down)": "Panel failure",
        "power outage": "Power outage at facility",
        "electrical fire": "Electrical fire or spark",
        "live wire": "Live wire exposure",
        "server room.*cooling": "Server room cooling failure",
        "refrigerant leak": "Refrigerant leak",
        "co detector": "CO detector alarm",
        "generator failure": "Generator failure",
        "hvac.*failure": "HVAC system failure",
        "burning smell": "Burning smell from electrical panel"
    }
    for pattern, label in emergency_map.items():
        if re.search(pattern, text_lower):
            result["emergency_definition"].append(label)

    # --- Phone numbers and routing ---
    phone_contexts = re.findall(
        r'([^\n.]*(?:dispatch|on.call|emergency|tech|backup|primary|contact|number)[^\n.]*\d{3}[-.\s]?\d{3}[-.\s]?\d{4}[^\n.]*)',
        text, re.IGNORECASE
    )
    phones_ordered = []
    for ctx in phone_contexts:
        nums = re.findall(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', ctx)
        phones_ordered.extend(nums)

    # Fallback: find ALL phone numbers if contextual search found none
    if not phones_ordered:
        phones_ordered = re.findall(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', text)

    # Remove duplicates preserving order
    seen = set()
    unique_phones = []
    for p in phones_ordered:
        norm = re.sub(r'[-.\s]', '', p)
        if norm not in seen:
            seen.add(norm)
            unique_phones.append(p)

    if unique_phones:
        result["emergency_routing_rules"]["primary_contact"] = unique_phones[0]
        result["emergency_routing_rules"]["primary_phone"] = unique_phones[0]
        result["emergency_routing_rules"]["contact_order"] = unique_phones[:3]
    if len(unique_phones) > 1:
        result["emergency_routing_rules"]["secondary_phone"] = unique_phones[1]

    # Fallback message
    if re.search(r'call 911', text_lower):
        result["emergency_routing_rules"]["fallback"] = "Advise caller to contact 911 if in immediate danger. Inform them our team has been paged."
    elif re.search(r'paging|will be contacted|call.*back.*within', text_lower):
        m = re.search(r'(?:call.*?back|contacted|respond).*?within (\d+) minutes', text_lower)
        if m:
            result["emergency_routing_rules"]["fallback"] = f"Inform caller our team has been paged and will contact them within {m.group(1)} minutes."
        else:
            result["emergency_routing_rules"]["fallback"] = "Inform caller our team has been paged and will follow up as soon as possible."

    # --- Transfer timeout ---
    timeout_match = re.search(r'(\d+)\s*seconds?', text_lower)
    if timeout_match:
        result["call_transfer_rules"]["timeout_seconds"] = int(timeout_match.group(1))

    # Fail message — generate a CLEAN agent-facing message, not raw transcript
    if re.search(r'call.*back.*within (\d+) minutes', text_lower):
        m = re.search(r'call.*back.*within (\d+) minutes', text_lower)
        result["call_transfer_rules"]["on_fail_message"] = f"I was unable to reach our team directly, but your information has been recorded. Someone will call you back within {m.group(1)} minutes."
    elif re.search(r'getting someone out|help is on the way', text_lower):
        result["call_transfer_rules"]["on_fail_message"] = "I was unable to reach our team directly, but help is on the way. Your information has been recorded and someone will contact you shortly."
    elif re.search(r'team has been paged|will be notified', text_lower):
        result["call_transfer_rules"]["on_fail_message"] = "I was unable to reach our team directly, but they have been paged with your information. Someone will call you back as soon as possible."
    elif re.search(r'someone will (call|reach|contact)', text_lower):
        result["call_transfer_rules"]["on_fail_message"] = "I was unable to connect you directly. Your information has been recorded and someone will call you back shortly."

    # --- Integration constraints ---
    constraint_patterns = [
        (r"(?:do not|never|don'?t).*?(?:create|generate|auto.?creat).*?(?:job|work.?order|ticket).*?(?:servicetrade|servicetitan|automatically|auto)", 
         "Do not automatically create jobs/work orders in field service software"),
        (r"(?:servicetrade|servicetitan).*?(?:manually|human review|dispatcher handles)",
         "All job creation in ServiceTrade/ServiceTitan must be done manually"),
        (r"(?:never|do not|don'?t).*?give.*?(?:quote|pricing|estimate)",
         "Do not provide pricing quotes to callers"),
        (r"(?:never|do not|don'?t).*?give.*?(?:technician|tech).*?(?:name|number|cell)",
         "Do not give out technician names or direct contact numbers"),
        (r"(?:never|do not|don'?t).*?(?:book|schedule|calendar).*?(?:directly|automatically)",
         "Do not book or schedule appointments directly"),
        (r"(?:never|do not|don'?t).*?give.*?(?:time estimate|arrival time)",
         "Do not provide arrival time estimates unless specifically authorized"),
    ]
    for pattern, label in constraint_patterns:
        if re.search(pattern, text_lower):
            result["integration_constraints"].append(label)

    # Specific service integration mentions
    for service in ["servicetrade", "servicetitan", "quickbooks", "google calendar"]:
        if service in text_lower and service.replace(" ", "") not in " ".join(result["integration_constraints"]).lower():
            result["integration_constraints"].append(f"{service.title()} integration in use — see constraints above")

    # --- Non-emergency after hours ---
    if re.search(r'non.emergency|non emergency', text_lower):
        result["non_emergency_routing_rules"] = "Collect name, phone number, and description. Confirm follow-up during next business hours. Do not attempt transfer."

    # --- After/office hours summaries ---
    result["after_hours_flow_summary"] = (
        "Greet caller. Identify if emergency or non-emergency. "
        "If emergency: collect name, number, address, then attempt transfer per routing rules. "
        "If transfer fails: inform caller team has been paged. "
        "If non-emergency: collect details and confirm next-business-day callback."
    )
    result["office_hours_flow_summary"] = (
        "Greet caller professionally. Understand purpose. "
        "Collect name and callback number. "
        "Route to appropriate team member or log for follow-up."
    )

    # --- Special phrases / notes ---
    special_notes = []
    if re.search(r"help is on the way", text_lower):
        special_notes.append("End emergency calls with: 'Help is on the way'")
    if re.search(r"confirm.*callback.*number|always confirm.*number", text_lower):
        special_notes.append("Always confirm callback number before ending call")
    if re.search(r"arizona|phoenix.*no daylight|mountain standard year.round", text_lower):
        special_notes.append("Phoenix AZ: no daylight saving — stays on Mountain Standard Time year-round")
    if special_notes:
        result["notes"] = "; ".join(special_notes)

    # --- Questions/unknowns ---
    if not result["business_hours"]["start"]:
        result["questions_or_unknowns"].append("Exact business hours start/end time not confirmed")
    if not result["business_hours"]["timezone"]:
        result["questions_or_unknowns"].append("Timezone not specified")
    if not result["emergency_routing_rules"]["primary_phone"]:
        result["questions_or_unknowns"].append("Emergency contact phone numbers not provided")
    if not result["call_transfer_rules"]["timeout_seconds"]:
        result["questions_or_unknowns"].append("Transfer timeout duration not specified")
    if call_type == "demo" and not result["office_address"]:
        result["questions_or_unknowns"].append("Office address not confirmed (expected — demo call)")
    if call_type == "demo" and not result["emergency_definition"]:
        result["questions_or_unknowns"].append("Emergency definitions not fully specified (expected — demo call)")

    return result


def run_all():
    print("=" * 65)
    print("CLARA AUTOMATION — FULL SAMPLE DATASET RUN")
    print("Generating outputs for 5 demo + 5 onboarding transcripts")
    print("=" * 65)

    account_map = {}
    batch_summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "accounts": []
    }

    demo_files = sorted(DEMO_DIR.glob("demo_*.txt"))
    onboard_files = sorted(ONBOARD_DIR.glob("onboarding_*.txt"))

    # Pipeline A: all demo calls
    print("\n--- PIPELINE A: DEMO CALLS ---")
    for demo_file in demo_files:
        stem = demo_file.stem.replace("demo_", "")
        account_id = f"ACC_{stem.zfill(3)}"
        print(f"\n[Pipeline A] {demo_file.name} → {account_id}")

        with open(demo_file, encoding="utf-8") as f:
            transcript = f.read()

        memo = smart_extract(transcript, "demo")
        memo["account_id"] = account_id
        memo["source_file"] = demo_file.name
        memo["call_type"] = "demo"
        memo["extracted_at"] = datetime.now(timezone.utc).isoformat()

        agent_spec = generate_agent_spec(memo, account_id, version="v1")

        # Save
        out_path = OUTPUTS_DIR / account_id / "v1"
        out_path.mkdir(parents=True, exist_ok=True)
        with open(out_path / "memo.json", "w", encoding="utf-8") as f:
            json.dump(memo, f, indent=2, ensure_ascii=False)
        with open(out_path / "agent_spec.json", "w", encoding="utf-8") as f:
            json.dump(agent_spec, f, indent=2, ensure_ascii=False)
        with open(out_path / "meta.json", "w", encoding="utf-8") as f:
            json.dump({"account_id": account_id, "version": "v1", "company": memo.get("company_name"), "generated_at": datetime.now(timezone.utc).isoformat()}, f, indent=2)

        account_map[stem] = account_id
        print(f"  ✓ Company: {memo.get('company_name')}")
        print(f"  ✓ Services: {', '.join(memo.get('services_supported', []))}")
        print(f"  ✓ Unknowns: {len(memo.get('questions_or_unknowns', []))}")

    # Pipeline B: all onboarding calls
    print("\n--- PIPELINE B: ONBOARDING CALLS ---")
    for onboard_file in onboard_files:
        stem = onboard_file.stem.replace("onboarding_", "")
        account_id = account_map.get(stem)
        if not account_id:
            print(f"  ⚠ No matching demo for {onboard_file.name}, skipping")
            continue

        print(f"\n[Pipeline B] {onboard_file.name} → {account_id}")

        # Load v1
        with open(OUTPUTS_DIR / account_id / "v1" / "memo.json", encoding="utf-8") as f:
            v1_memo = json.load(f)

        with open(onboard_file, encoding="utf-8") as f:
            transcript = f.read()

        v2_raw = smart_extract(transcript, "onboarding")

        # Smart merge: onboarding data wins, but don't overwrite with nulls
        # Lists use UNION strategy — don't lose v1 data
        merged = json.loads(json.dumps(v1_memo))  # deep copy
        for key, val in v2_raw.items():
            if key in {"_extraction_method", "extracted_at", "source_file", "call_type", "account_id"}:
                merged[key] = val
                continue
            if val is None or val == "":
                continue
            if isinstance(val, list):
                if val:  # non-empty list from onboarding
                    existing = merged.get(key, [])
                    if isinstance(existing, list):
                        # Union: keep all v1 items + add new v2 items
                        combined = list(existing)
                        for item in val:
                            if item not in combined:
                                combined.append(item)
                        merged[key] = combined
                    else:
                        merged[key] = val
                # empty list from onboarding: keep v1 data
                continue
            if isinstance(val, dict) and isinstance(merged.get(key), dict):
                for dk, dv in val.items():
                    if dv is not None and dv != [] and dv != "":
                        merged[key][dk] = dv
            else:
                merged[key] = val

        merged["account_id"] = account_id
        merged["version"] = "v2"
        merged["call_type"] = "onboarding"
        merged["source_file"] = onboard_file.name
        merged["extracted_at"] = datetime.now(timezone.utc).isoformat()
        merged["version_history"] = {
            "v1_generated_at": v1_memo.get("extracted_at"),
            "v2_generated_at": datetime.now(timezone.utc).isoformat()
        }

        # Re-evaluate questions_or_unknowns after merge
        resolved_unknowns = []
        if merged.get("business_hours", {}).get("start"):
            resolved_unknowns.append("Exact business hours start/end time not confirmed")
        if merged.get("business_hours", {}).get("timezone"):
            resolved_unknowns.append("Timezone not specified")
        if merged.get("emergency_routing_rules", {}).get("primary_phone"):
            resolved_unknowns.append("Emergency contact phone numbers not provided")
        if merged.get("call_transfer_rules", {}).get("timeout_seconds"):
            resolved_unknowns.append("Transfer timeout duration not specified")
        if merged.get("office_address"):
            resolved_unknowns.append("Office address not confirmed (expected — demo call)")
        if merged.get("emergency_definition"):
            resolved_unknowns.append("Emergency definitions not fully specified (expected — demo call)")
        merged["questions_or_unknowns"] = [
            q for q in merged.get("questions_or_unknowns", [])
            if q not in resolved_unknowns
        ]

        agent_spec_v2 = generate_agent_spec(merged, account_id, version="v2")
        changelog = generate_changelog(v1_memo, merged, account_id)
        changelog_md = generate_markdown_changelog(changelog)

        # Save v2
        v2_path = OUTPUTS_DIR / account_id / "v2"
        v2_path.mkdir(parents=True, exist_ok=True)
        with open(v2_path / "memo.json", "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        with open(v2_path / "agent_spec.json", "w", encoding="utf-8") as f:
            json.dump(agent_spec_v2, f, indent=2, ensure_ascii=False)
        with open(v2_path / "meta.json", "w", encoding="utf-8") as f:
            json.dump({"account_id": account_id, "version": "v2", "company": merged.get("company_name"), "generated_at": datetime.now(timezone.utc).isoformat(), "total_changes": changelog["total_changes"]}, f, indent=2)

        # Save changelog
        cl_path = OUTPUTS_DIR / account_id / "changelog"
        cl_path.mkdir(parents=True, exist_ok=True)
        with open(cl_path / "changes.json", "w", encoding="utf-8") as f:
            json.dump(changelog, f, indent=2, ensure_ascii=False)
        with open(cl_path / "changes.md", "w", encoding="utf-8") as f:
            f.write(changelog_md)

        batch_summary["accounts"].append({
            "account_id": account_id,
            "company": merged.get("company_name"),
            "v1_unknowns": len(v1_memo.get("questions_or_unknowns", [])),
            "v2_unknowns": len(merged.get("questions_or_unknowns", [])),
            "total_changes": changelog["total_changes"],
            "critical_changes": changelog["critical_changes"]
        })

        print(f"  ✓ Company: {merged.get('company_name')}")
        print(f"  ✓ Changes: {changelog['total_changes']} total ({changelog['critical_changes']} critical)")
        print(f"  ✓ Remaining unknowns: {len(merged.get('questions_or_unknowns', []))}")

    # Save batch report
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUTS_DIR / ".." / "batch_report.json", "w", encoding="utf-8") as f:
        json.dump(batch_summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print("ALL DONE ✓")
    print(f"Outputs in: {OUTPUTS_DIR}")
    print("=" * 65)


if __name__ == "__main__":
    run_all()
