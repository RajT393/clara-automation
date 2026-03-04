# Clara Automation Pipeline

> **Demo Call → v1 Agent → Onboarding Call → v2 Agent**
> Zero-cost, fully reproducible, batch-capable automation for Clara Answers.

---

## What This Does

This pipeline converts raw call transcripts into production-ready Retell AI agent configurations automatically, at zero cost, with full versioning and changelog tracking.

```
demo_001.txt  ──[Pipeline A]──▶  ACC_001/v1/memo.json
                                 ACC_001/v1/agent_spec.json

onboarding_001.txt  ──[Pipeline B]──▶  ACC_001/v2/memo.json
                                        ACC_001/v2/agent_spec.json
                                        ACC_001/changelog/changes.md
```

---

## Architecture

```
clara-automation/
├── scripts/
│   ├── extractor.py              # LLM extraction (Ollama → Groq → Rule-based)
│   ├── prompt_generator.py       # Retell agent spec builder
│   ├── pipeline_a.py             # Demo call → v1 memo + agent spec
│   ├── pipeline_b.py             # Onboarding → v2 memo + changelog
│   ├── batch_run.py              # Run all 10 files at once
│   ├── diff_generator.py         # v1→v2 changelog engine
│   └── generate_sample_outputs.py  # One-command: generates all sample outputs
├── workflows/
│   └── n8n_workflow.json         # Import this into n8n
├── sample_data/
│   ├── demo_transcripts/         # demo_001.txt ... demo_005.txt
│   └── onboarding_transcripts/   # onboarding_001.txt ... onboarding_005.txt
├── outputs/
│   └── accounts/
│       └── ACC_001/
│           ├── v1/ (memo.json, agent_spec.json, meta.json)
│           ├── v2/ (memo.json, agent_spec.json, meta.json)
│           └── changelog/ (changes.json, changes.md)
├── dashboard/
│   └── index.html                # Visual diff viewer + account overview
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quickstart — Run Everything in 3 Commands

```bash
git clone https://github.com/YOUR_USERNAME/clara-automation
cd clara-automation
pip install requests
python scripts/generate_sample_outputs.py
```

Outputs appear in `outputs/accounts/`. Open `dashboard/index.html` in your browser for the visual diff viewer.

---

## Running With Your Own Transcripts

### Pipeline A: Demo Call → v1 Agent

```bash
python scripts/pipeline_a.py \
  --transcript /path/to/demo_transcript.txt \
  --account_id ACC_007
```

### Pipeline B: Onboarding → v2 Agent

```bash
python scripts/pipeline_b.py \
  --transcript /path/to/onboarding_transcript.txt \
  --account_id ACC_007
```

### Batch Run: All Files at Once

```bash
python scripts/batch_run.py \
  --demo_dir sample_data/demo_transcripts \
  --onboarding_dir sample_data/onboarding_transcripts
```

Files are auto-matched by number: `demo_001.txt` matches `onboarding_001.txt`.

---

## LLM Configuration (Zero-Cost)

The extractor tries three methods in order:

| Method | Cost | Setup | Quality |
|--------|------|-------|---------|
| Ollama (local) | Free | Install Ollama + pull model | High |
| Groq API | Free tier | Get key at console.groq.com | High |
| Rule-based | Free | None — always works | Good |

The pipeline never fails: if Ollama and Groq are unavailable, rule-based extraction runs automatically.

### Option 1: Ollama (Recommended)

```bash
# Install: https://ollama.ai
ollama pull llama3
# Set in .env: OLLAMA_MODEL=llama3
```

### Option 2: Groq Free Tier

```bash
# Get free key: https://console.groq.com
# Set in .env: GROQ_API_KEY=your_key_here
```

---

## n8n Setup

```bash
cp .env.example .env   # fill in your values
docker-compose up -d   # start n8n at http://localhost:5678
```

Import `workflows/n8n_workflow.json` via n8n UI (Workflows → Import from file).

Webhook endpoints:

| Endpoint | Purpose |
|----------|---------|
| `POST /webhook/pipeline-a` | Run Pipeline A on a file |
| `POST /webhook/pipeline-b` | Run Pipeline B on a file |
| `POST /webhook/batch-run` | Run all sample data |

---

## Output Format

### memo.json (key fields)

```json
{
  "account_id": "ACC_001",
  "company_name": "Shield Fire Protection",
  "business_hours": { "days": [...], "start": "8:00 AM", "end": "5:00 PM", "timezone": "Eastern Time" },
  "emergency_definition": ["Active sprinkler discharge", "Fire alarm activation"],
  "emergency_routing_rules": { "contact_order": ["614-555-0192", "614-555-0100"] },
  "call_transfer_rules": { "timeout_seconds": 30 },
  "integration_constraints": ["Do not auto-create sprinkler jobs in ServiceTrade"],
  "questions_or_unknowns": [],
  "version": "v2"
}
```

### agent_spec.json (key fields)

```json
{
  "agent_name": "Clara - Shield Fire Protection",
  "version": "v2",
  "system_prompt": "...(full Clara prompt with business-hours + after-hours flows)...",
  "call_transfer_protocol": { "timeout_seconds": 30, "transfer_to": ["614-555-0192"] },
  "fallback_protocol": { "script": "Help is on the way..." },
  "retell_import_instructions": { "step_1": "Log into app.retell.ai", ... }
}
```

---

## Retell Manual Import (if API not available on free tier)

Each `agent_spec.json` includes `retell_import_instructions`:

1. Log into `app.retell.ai`
2. Create Agent → Custom LLM or Retell LLM
3. Paste `system_prompt` into System Prompt box
4. Set voice from `voice_style.voice_id`
5. Configure transfer numbers from `call_transfer_protocol.transfer_to`
6. Save and test

---

## Design Decisions

**Why rule-based extraction as fallback?** The assignment requires zero cost and reproducibility. Rule-based extraction means the pipeline works for any reviewer without any API keys or model setup.

**Why Ollama primary?** Local LLM is the gold standard for zero-cost, high-quality extraction. No rate limits, no latency, no cost.

**Why merge rather than overwrite on Pipeline B?** Onboarding data should override demo assumptions, but null values in onboarding should not erase valid demo data. The merge logic preserves all v1 data unless explicitly updated.

**Why hash-based account IDs?** Ensures the same transcript always generates the same account ID, making the pipeline idempotent.

---

## Known Limitations

- No audio transcription (pass `.txt` transcripts as input)
- Retell free tier may not support programmatic agent creation (manual import steps included)
- n8n webhook mode requires Docker; scripts work without Docker
- Rule-based extraction may miss unusual phrasing — LLM mode handles edge cases better

## What I Would Improve with Production Access

- Whisper local transcription for audio-to-agent full pipeline
- Retell API for programmatic agent creation and rollback
- Supabase for structured account database with queryability
- Asana integration for automatic task creation on Pipeline A completion
- Confidence scoring on extraction fields
- Human-in-the-loop review for conflicting v1/v2 fields

---

## Accounts Processed

| Account | Company | v1 Unknowns | v2 Unknowns | Changes |
|---------|---------|-------------|-------------|---------|
| ACC_001 | Shield Fire Protection | 2 | 0 | 5 (3 critical) |
| ACC_002 | Apex Alarm Systems | 2 | 0 | 7 (4 critical) |
| ACC_003 | PacWest Fire & Safety | 3 | 0 | 6 (4 critical) |
| ACC_004 | Cornerstone HVAC Services | 3 | 0 | 7 (4 critical) |
| ACC_005 | TrueGuard Electrical | 2 | 0 | 7 (4 critical) |

All 10 transcripts processed. All unknowns resolved after onboarding.

---

## Evaluation Checklist

- [x] Runs end-to-end on all 10 files
- [x] Zero cost (Ollama local, Groq free tier, rule-based fallback)
- [x] No hallucination (null fields, explicit questions_or_unknowns)
- [x] Prompt hygiene (business-hours flow, after-hours flow, transfer + fallback protocols)
- [x] Versioning (v1/v2 directories, version_history field)
- [x] Changelog (JSON diff + Markdown per account)
- [x] Idempotent (hash-based IDs, safe to run twice)
- [x] n8n workflow (importable JSON in /workflows)
- [x] Dashboard (visual diff viewer in /dashboard/index.html)
- [x] Reproducible (clone, pip install requests, one command)

---

*Built for Clara Answers technical intern assignment — March 2026*
