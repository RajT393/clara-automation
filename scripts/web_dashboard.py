"""
web_dashboard.py - Clara Automation Pipeline Web Dashboard
Run: python scripts/web_dashboard.py
Open: http://localhost:8080
"""

import json
import os
import sys

# CRITICAL: Always resolve paths relative to THIS script's location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs", "accounts")

try:
    from flask import Flask, jsonify, render_template_string
except ImportError:
    print("ERROR: Flask is required for the web dashboard.")
    print("Install it with: pip install flask")
    sys.exit(1)

app = Flask(__name__)


def get_accounts():
    accounts = []
    if not os.path.exists(OUTPUTS_DIR):
        return accounts
    for account_id in sorted(os.listdir(OUTPUTS_DIR)):
        acc_dir = os.path.join(OUTPUTS_DIR, account_id)
        if not os.path.isdir(acc_dir):
            continue
        versions = [d for d in os.listdir(acc_dir) if os.path.isdir(os.path.join(acc_dir, d))]
        memo = load_json(account_id, "v2", "memo.json") or load_json(account_id, "v1", "memo.json") or {}
        accounts.append({
            "account_id": account_id,
            "company_name": memo.get("company_name") or account_id,
            "versions_present": sorted(versions),
            "has_v2": "v2" in versions,
            "open_questions": len(memo.get("questions_or_unknowns") or [])
        })
    return accounts


def load_json(account_id, version, filename):
    path = os.path.join(OUTPUTS_DIR, account_id, version, filename)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(account_id, version, filename):
    path = os.path.join(OUTPUTS_DIR, account_id, version, filename)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Clara Automation Pipeline</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
header { background: linear-gradient(135deg, #1e40af, #7c3aed); padding: 24px 32px; }
header h1 { font-size: 1.6rem; font-weight: 700; }
header p { font-size: 0.9rem; opacity: 0.8; margin-top: 4px; }
.badge { background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin-left: 12px; }
main { padding: 32px; max-width: 1200px; margin: 0 auto; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 32px; }
.stat-card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; text-align: center; }
.stat-card .num { font-size: 2.5rem; font-weight: 800; color: #60a5fa; }
.stat-card .label { font-size: 0.75rem; color: #94a3b8; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
.section-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 16px; color: #cbd5e1; }
.accounts-grid { display: grid; gap: 12px; }
.account-card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; cursor: pointer; transition: all 0.2s; }
.account-card:hover { border-color: #60a5fa; transform: translateY(-1px); }
.account-card.has-v2 { border-left: 4px solid #22c55e; }
.account-card.v1-only { border-left: 4px solid #f59e0b; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }
.company-name { font-size: 1rem; font-weight: 600; }
.account-id { font-size: 0.72rem; color: #64748b; margin-top: 2px; }
.vbadge { padding: 3px 10px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; }
.v2b { background: #14532d; color: #4ade80; }
.v1b { background: #451a03; color: #fb923c; }
.card-meta { font-size: 0.78rem; color: #94a3b8; }
.warn { color: #f59e0b; font-size: 0.75rem; margin-top: 6px; }
.overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.75); z-index: 100; align-items: center; justify-content: center; }
.overlay.open { display: flex; }
.modal { background: #1e293b; border: 1px solid #334155; border-radius: 16px; width: 92%; max-width: 820px; max-height: 88vh; overflow-y: auto; padding: 28px; }
.modal-title { font-size: 1.2rem; font-weight: 700; }
.modal-sub { font-size: 0.78rem; color: #64748b; margin-top: 3px; margin-bottom: 20px; }
.close-btn { float: right; background: #334155; border: none; color: #e2e8f0; padding: 7px 16px; border-radius: 8px; cursor: pointer; }
.tabs { display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; }
.tab { padding: 7px 18px; border-radius: 8px; cursor: pointer; font-size: 0.82rem; border: 1px solid #334155; background: transparent; color: #94a3b8; }
.tab.active { background: #1e40af; border-color: #1e40af; color: white; }
.tab-pane { display: none; }
.tab-pane.active { display: block; }
pre { background: #0f172a; padding: 16px; border-radius: 8px; font-size: 0.72rem; overflow-x: auto; white-space: pre-wrap; color: #a5f3fc; line-height: 1.5; }
.diff-item { background: #0f172a; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px; }
.diff-field { font-weight: 600; color: #60a5fa; margin-bottom: 6px; font-size: 0.82rem; }
.diff-old { color: #f87171; font-size: 0.78rem; }
.diff-new { color: #4ade80; font-size: 0.78rem; }
.empty { text-align: center; padding: 60px; color: #475569; }
.prompt-box { background: #0f172a; padding: 16px; border-radius: 8px; font-size: 0.72rem; white-space: pre-wrap; color: #e2e8f0; line-height: 1.6; max-height: 400px; overflow-y: auto; }
</style>
</head>
<body>
<header>
  <h1>⚡ Clara Automation Pipeline <span class="badge">Zero-Cost Stack</span></h1>
  <p>Demo Call → Agent v1 → Onboarding → Agent v2</p>
</header>
<main>
  <div class="stats" id="stats"><div class="stat-card"><div class="num">...</div><div class="label">Loading</div></div></div>
  <div class="section-title">Processed Accounts</div>
  <div class="accounts-grid" id="accounts"><div class="empty">Loading accounts...</div></div>
</main>

<div class="overlay" id="overlay">
  <div class="modal">
    <button class="close-btn" onclick="closeModal()">✕ Close</button>
    <div class="modal-title" id="m-company"></div>
    <div class="modal-sub" id="m-id"></div>
    <div class="tabs">
      <button class="tab active" onclick="switchTab(event,'pane-memo')">📋 Account Memo</button>
      <button class="tab" onclick="switchTab(event,'pane-spec')">🤖 Agent Spec</button>
      <button class="tab" onclick="switchTab(event,'pane-prompt')">💬 System Prompt</button>
      <button class="tab" onclick="switchTab(event,'pane-diff')">🔀 v1 → v2 Diff</button>
    </div>
    <div id="pane-memo" class="tab-pane active"><pre id="c-memo"></pre></div>
    <div id="pane-spec" class="tab-pane"><pre id="c-spec"></pre></div>
    <div id="pane-prompt" class="tab-pane"><div class="prompt-box" id="c-prompt"></div></div>
    <div id="pane-diff" class="tab-pane"><div id="c-diff"></div></div>
  </div>
</div>

<script>
let accounts = [];

async function load() {
  try {
    const res = await fetch('/api/accounts');
    accounts = await res.json();
    renderStats();
    renderAccounts();
  } catch(e) {
    document.getElementById('accounts').innerHTML = '<div class="empty">Error loading data: ' + e.message + '</div>';
  }
}

function renderStats() {
  const total = accounts.length;
  const v2 = accounts.filter(a => a.has_v2).length;
  const openQ = accounts.reduce((s,a) => s + a.open_questions, 0);
  document.getElementById('stats').innerHTML = `
    <div class="stat-card"><div class="num">${total}</div><div class="label">Total Accounts</div></div>
    <div class="stat-card"><div class="num">${v2}</div><div class="label">Fully Onboarded</div></div>
    <div class="stat-card"><div class="num">${total - v2}</div><div class="label">Demo Only</div></div>
    <div class="stat-card"><div class="num">${openQ}</div><div class="label">Open Questions</div></div>
  `;
}

function renderAccounts() {
  if (!accounts.length) {
    document.getElementById('accounts').innerHTML = '<div class="empty">No accounts found. Run batch_run.py first.</div>';
    return;
  }
  document.getElementById('accounts').innerHTML = accounts.map(a => `
    <div class="account-card ${a.has_v2 ? 'has-v2' : 'v1-only'}" onclick="openModal('${a.account_id}')">
      <div class="card-header">
        <div>
          <div class="company-name">${a.company_name}</div>
          <div class="account-id">${a.account_id}</div>
        </div>
        <span class="vbadge ${a.has_v2 ? 'v2b' : 'v1b'}">${a.has_v2 ? 'v1 + v2 ✓' : 'v1 only'}</span>
      </div>
      <div class="card-meta">Versions: ${a.versions_present.join(', ')} &nbsp;|&nbsp; Questions: ${a.open_questions > 0 ? '<span style="color:#f59e0b">'+a.open_questions+' open</span>' : '<span style="color:#4ade80">none</span>'}</div>
      ${a.open_questions > 0 ? '<div class="warn">⚠ Review before deploying to Retell</div>' : ''}
    </div>
  `).join('');
}

async function openModal(id) {
  const acc = accounts.find(a => a.account_id === id);
  document.getElementById('m-company').textContent = acc.company_name;
  document.getElementById('m-id').textContent = id;
  document.getElementById('c-memo').textContent = 'Loading...';
  document.getElementById('c-spec').textContent = 'Loading...';
  document.getElementById('c-prompt').textContent = 'Loading...';
  document.getElementById('c-diff').innerHTML = 'Loading...';
  document.getElementById('overlay').classList.add('open');

  const res = await fetch('/api/account/' + id);
  const d = await res.json();

  // Memo
  const memo = d.memo_v2 || d.memo_v1 || {};
  document.getElementById('c-memo').textContent = JSON.stringify(memo, null, 2);

  // Spec (without system prompt)
  const spec = d.spec_v2 || d.spec_v1 || {};
  const specDisplay = Object.fromEntries(Object.entries(spec).filter(([k]) => k !== 'system_prompt'));
  document.getElementById('c-spec').textContent = JSON.stringify(specDisplay, null, 2);

  // System prompt
  const prompt = (d.spec_v2 || d.spec_v1 || {}).system_prompt || 'No system prompt found';
  document.getElementById('c-prompt').textContent = prompt;

  // Diff
  if (d.changes && d.changes.length > 0) {
    document.getElementById('c-diff').innerHTML = 
      '<div style="color:#94a3b8;font-size:0.8rem;margin-bottom:12px;">'+d.changes.length+' changes from v1 → v2</div>' +
      d.changes.map(c => `
        <div class="diff-item">
          <div class="diff-field">📝 ${c.field} <span style="color:#64748b;font-weight:400;">[${c.change_type}]</span></div>
          ${c.old_value !== null && c.old_value !== undefined ? '<div class="diff-old">− ' + JSON.stringify(c.old_value) + '</div>' : ''}
          ${c.new_value !== null && c.new_value !== undefined ? '<div class="diff-new">+ ' + JSON.stringify(c.new_value) + '</div>' : ''}
        </div>`).join('');
  } else {
    document.getElementById('c-diff').innerHTML = '<div class="empty" style="padding:20px">No v2 changes recorded for this account</div>';
  }
}

function closeModal() { document.getElementById('overlay').classList.remove('open'); }
function switchTab(e, paneId) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  e.target.classList.add('active');
  document.getElementById(paneId).classList.add('active');
}
document.getElementById('overlay').addEventListener('click', function(e) { if (e.target === this) closeModal(); });
load();
</script>
</body>
</html>'''


@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/api/accounts')
def api_accounts():
    return jsonify(get_accounts())


@app.route('/api/account/<account_id>')
def api_account(account_id):
    changes_data = load_json(account_id, 'v2', 'changes.json')
    return jsonify({
        'memo_v1': load_json(account_id, 'v1', 'memo.json'),
        'memo_v2': load_json(account_id, 'v2', 'memo.json'),
        'spec_v1': load_json(account_id, 'v1', 'agent_spec.json'),
        'spec_v2': load_json(account_id, 'v2', 'agent_spec.json'),
        'changes': (changes_data or {}).get('changes') if changes_data else []
    })


if __name__ == '__main__':
    print(f"\n Project root: {PROJECT_ROOT}")
    print(f" Outputs dir: {OUTPUTS_DIR}")
    print(f" Accounts found: {len(get_accounts())}")
    accs = get_accounts()
    for a in accs:
        print(f"   ✓ {a['account_id']} ({a['company_name']})")
    print(f"\n Clara Dashboard → http://localhost:8080\n")
    app.run(host='0.0.0.0', port=8080, debug=False)
    