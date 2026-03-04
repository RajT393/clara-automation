"""
extractor.py
Extracts structured account memo from transcript using Ollama (local LLM).
Falls back to Groq free API, then pure rule-based extraction.
Zero-cost. No paid APIs required.
"""

import json
import re
import requests
import os
from typing import Optional

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

EXTRACTION_PROMPT = """You are a structured data extractor for Clara Answers, an AI voice agent configuration system.
Extract operational configuration data from the call transcript below.

STRICT RULES:
- Only extract what is EXPLICITLY stated. Never invent or assume values.
- If a field is not mentioned, set it to null.
- Unclear items go into questions_or_unknowns.
- Return ONLY valid JSON. No explanation. No markdown. No extra text.

Return this exact JSON schema:
{
  "company_name": null,
  "business_hours": {
    "days": null,
    "start": null,
    "end": null,
    "timezone": null
  },
  "office_address": null,
  "services_supported": [],
  "emergency_definition": [],
  "emergency_routing_rules": {
    "primary_contact": null,
    "primary_phone": null,
    "secondary_contact": null,
    "secondary_phone": null,
    "fallback": null
  },
  "non_emergency_routing_rules": null,
  "call_transfer_rules": {
    "timeout_seconds": null,
    "retries": null,
    "on_fail_message": null
  },
  "integration_constraints": [],
  "after_hours_flow_summary": null,
  "office_hours_flow_summary": null,
  "questions_or_unknowns": [],
  "notes": null
}

TRANSCRIPT:
{transcript}
"""


def extract_with_ollama(transcript: str) -> Optional[dict]:
    try:
        prompt = EXTRACTION_PROMPT.replace("{transcript}", transcript)
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.1}},
            timeout=120
        )
        if response.status_code == 200:
            raw = response.json().get("response", "")
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
    except Exception as e:
        print(f"[Ollama] Failed: {e}")
    return None


def extract_with_groq(transcript: str) -> Optional[dict]:
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return None
    try:
        prompt = EXTRACTION_PROMPT.replace("{transcript}", transcript)
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={"model": "llama3-8b-8192", "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.1},
            timeout=60
        )
        if response.status_code == 200:
            raw = response.json()["choices"][0]["message"]["content"]
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
    except Exception as e:
        print(f"[Groq] Failed: {e}")
    return None


def extract_rule_based(transcript: str) -> dict:
    """Pure rule-based fallback. No LLM needed. Always returns valid dict."""
    result = {
        "company_name": None,
        "business_hours": {"days": None, "start": None, "end": None, "timezone": None},
        "office_address": None,
        "services_supported": [],
        "emergency_definition": [],
        "emergency_routing_rules": {
            "primary_contact": None, "primary_phone": None,
            "secondary_contact": None, "secondary_phone": None, "fallback": None
        },
        "non_emergency_routing_rules": None,
        "call_transfer_rules": {"timeout_seconds": None, "retries": None, "on_fail_message": None},
        "integration_constraints": [],
        "after_hours_flow_summary": None,
        "office_hours_flow_summary": None,
        "questions_or_unknowns": [],
        "notes": "Extracted via rule-based fallback. Manual review recommended."
    }

    t = transcript.lower()

    # Company name
    for pat in [
        r"(?:this is|from|we are|company is|called|i'm with)\s+([A-Z][A-Za-z\s&]+(?:LLC|Inc|Corp|Co\.?|Services|Protection|Fire|Systems|Alarm)?)",
        r"([A-Z][A-Za-z\s&]+(?:Fire Protection|Fire Systems|Sprinkler|Alarm|HVAC|Services))"
    ]:
        m = re.search(pat, transcript)
        if m:
            result["company_name"] = m.group(1).strip()
            break

    # Days
    m = re.search(r"(monday|mon)\s*(?:through|to|-)\s*(friday|fri|saturday|sat|sunday|sun)", t)
    if m:
        result["business_hours"]["days"] = m.group(0).title()

    # Hours
    m = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*(?:to|-)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))", t)
    if m:
        result["business_hours"]["start"] = m.group(1).upper()
        result["business_hours"]["end"] = m.group(2).upper()

    # Timezone
    for k, v in {"eastern": "America/New_York", "est": "America/New_York", "central": "America/Chicago",
                 "cst": "America/Chicago", "mountain": "America/Denver", "pacific": "America/Los_Angeles",
                 "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles"}.items():
        if k in t:
            result["business_hours"]["timezone"] = v
            break

    # Services
    result["services_supported"] = [s for s in [
        "fire protection", "sprinkler", "fire alarm", "suppression", "hvac",
        "electrical", "inspection", "extinguisher", "backflow", "monitoring"
    ] if s in t]

    # Emergency triggers
    result["emergency_definition"] = [e for e in [
        "sprinkler leak", "pipe burst", "fire alarm triggered", "smoke", "flood",
        "water leak", "system failure", "fire"
    ] if e in t]

    # Phones
    phones = re.findall(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", transcript)
    if phones:
        result["emergency_routing_rules"]["primary_phone"] = phones[0]
    if len(phones) > 1:
        result["emergency_routing_rules"]["secondary_phone"] = phones[1]

    # Timeout
    m = re.search(r"(\d+)\s*seconds?", t)
    if m:
        result["call_transfer_rules"]["timeout_seconds"] = int(m.group(1))

    # Integration constraints
    if "servicetrade" in t:
        m = re.search(r"(?:never|do not|don't) create[^.]+\.", transcript, re.IGNORECASE)
        if m:
            result["integration_constraints"].append(m.group(0).strip())
        else:
            result["integration_constraints"].append("ServiceTrade integration mentioned - review constraints")

    # Flag unknowns
    unknowns = []
    if not result["company_name"]:
        unknowns.append("Company name not clearly stated")
    if not result["business_hours"]["timezone"]:
        unknowns.append("Timezone not confirmed")
    if not result["emergency_routing_rules"]["primary_phone"]:
        unknowns.append("Emergency contact phone number missing")
    if not result["business_hours"]["start"]:
        unknowns.append("Business hours not confirmed")
    if not result["emergency_definition"]:
        unknowns.append("Emergency trigger conditions not clearly defined")
    result["questions_or_unknowns"] = unknowns

    return result


def extract_from_transcript(transcript: str, source: str = "demo") -> dict:
    """
    Main extraction entry point.
    Priority: Ollama (local) -> Groq (free API) -> Rule-based
    """
    print(f"[Extractor] Starting extraction (source={source})...")

    result = extract_with_ollama(transcript)
    if result:
        print("[Extractor] SUCCESS via Ollama (local LLM)")
        result["_extraction_method"] = "ollama"
        return result

    result = extract_with_groq(transcript)
    if result:
        print("[Extractor] SUCCESS via Groq (free API)")
        result["_extraction_method"] = "groq"
        return result

    print("[Extractor] Using rule-based fallback")
    result = extract_rule_based(transcript)
    result["_extraction_method"] = "rule_based"
    return result
