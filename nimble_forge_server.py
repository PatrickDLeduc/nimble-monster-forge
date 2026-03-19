#!/usr/bin/env python3
"""
Nimble Monster Forge — Server with Observability
Run: python nimble_forge_server.py
Then open: http://localhost:8000
Admin: http://localhost:8000/admin
"""

import json
import http.server
import urllib.request
import urllib.error
import os
import re
import time
import threading
import base64

# ── Prometheus Instrumentation ─────────────────────────────────────────────
from prometheus_client import (
    Counter, Histogram, Gauge, Info,
    generate_latest, CONTENT_TYPE_LATEST
)

REQUESTS_TOTAL = Counter(
    "forge_requests_total",
    "Total HTTP requests",
    ["endpoint", "method", "status"]
)

REQUEST_DURATION = Histogram(
    "forge_request_duration_seconds",
    "Request latency in seconds",
    ["endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

ACTIVE_SESSIONS = Gauge(
    "forge_active_sessions",
    "Approximate concurrent users (unique IPs in last 5 min)"
)

ANTHROPIC_TOKENS = Counter(
    "forge_anthropic_tokens_total",
    "Tokens consumed from Anthropic API",
    ["direction"]  # input / output
)

ANTHROPIC_COST = Counter(
    "forge_anthropic_cost_dollars",
    "Cumulative Anthropic API cost in USD"
)

GENERATION_TOTAL = Counter(
    "forge_generation_total",
    "Total monster generations",
    ["legendary"]
)

MONSTER_OPTIONS = Counter(
    "forge_monster_options",
    "Feature selections for monster generation",
    ["option_type", "option_value"]
)

AIRTABLE_SAVES = Counter(
    "forge_airtable_saves_total",
    "Airtable save attempts",
    ["status"]  # success / error
)

ERRORS_TOTAL = Counter(
    "forge_errors_total",
    "Error occurrences",
    ["error_type", "endpoint"]
)

APP_INFO = Info("forge", "Application metadata")
APP_INFO.info({
    "version": "1.1.0",
    "app": "nimble_monster_forge",
    "stack": "python_stdlib"
})

# ── Session Tracking ───────────────────────────────────────────────────────
SESSION_WINDOW = 300  # 5 minutes
_session_lock = threading.Lock()
_session_hits = {}  # ip -> last_seen_timestamp


def _track_session(ip):
    """Record an IP hit and update the active sessions gauge."""
    now = time.time()
    with _session_lock:
        _session_hits[ip] = now
        cutoff = now - SESSION_WINDOW
        expired = [k for k, v in _session_hits.items() if v < cutoff]
        for k in expired:
            del _session_hits[k]
        ACTIVE_SESSIONS.set(len(_session_hits))


# ── Anthropic Pricing (Sonnet 4) ──────────────────────────────────────────
INPUT_COST_PER_TOKEN = 3.0 / 1_000_000
OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000


# ── Grafana Cloud Metrics Endpoint (Pull-based) ───────────────────────────
# Grafana Cloud scrapes your /metrics endpoint directly via their
# "Metrics Endpoint" integration. A bearer token protects the endpoint.
METRICS_BEARER_TOKEN = os.environ.get("METRICS_BEARER_TOKEN", "")


# ── Invite Code System ────────────────────────────────────────────────────
# Format: "code1:limit1,code2:limit2" e.g. "dragon:50,phoenix:50,Mellon:100"
# Users enter an invite code instead of their own API key.
# The server uses ANTHROPIC_API_KEY to make calls on their behalf.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
INVITE_CODES_RAW = os.environ.get("INVITE_CODES", "")

_invite_lock = threading.Lock()
_invite_codes = {}   # code -> max_uses
_invite_usage = {}   # code -> current_count

def _parse_invite_codes():
    """Parse INVITE_CODES env var into code->limit dict."""
    if not INVITE_CODES_RAW:
        return
    for entry in INVITE_CODES_RAW.split(","):
        entry = entry.strip()
        if ":" in entry:
            code, limit = entry.rsplit(":", 1)
            try:
                _invite_codes[code.strip()] = int(limit.strip())
                _invite_usage[code.strip()] = 0
            except ValueError:
                print(f"  [invite] Warning: invalid limit for code '{code}', skipping")

_parse_invite_codes()

INVITE_USAGE = Counter(
    "forge_invite_usage_total",
    "Invite code usage",
    ["code"]
)


# ── Admin Dashboard HTML ──────────────────────────────────────────────────
ADMIN_KEY = os.environ.get("ADMIN_KEY", "nimbleforge")
GRAFANA_DASHBOARD_URL = os.environ.get("GRAFANA_DASHBOARD_URL", "")

ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nimble Monster Forge — Admin</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500&family=Outfit:wght@300;400;500;600&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#0c0e14;color:#c8cdd8;font-family:'Outfit',sans-serif;min-height:100vh;padding:24px}
  .wrap{max-width:1200px;margin:0 auto}
  h1{font-size:20px;font-weight:600;color:#e8ecf4;margin-bottom:4px}
  .sub{font-family:'JetBrains Mono',monospace;font-size:12px;color:#6b7280;margin-bottom:24px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:24px}
  .card{background:#13161f;border:1px solid #252a3a;border-radius:10px;padding:20px}
  .card-title{font-family:'JetBrains Mono',monospace;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
  .card-value{font-size:28px;font-weight:600;color:#e8ecf4}
  .accent{color:#e8a825}
  .green{color:#34d399}
  .blue{color:#60a5fa}
  .grafana-frame{width:100%;height:400px;border:1px solid #252a3a;border-radius:10px;background:#13161f;margin-bottom:16px}
  .hint{font-family:'JetBrains Mono',monospace;font-size:11px;color:#6b7280;margin-top:8px;padding:12px;background:#13161f;border:1px solid #252a3a;border-radius:8px;line-height:1.8}
  .back{color:#6b7280;text-decoration:none;font-size:13px;display:inline-block;margin-bottom:16px}
  .back:hover{color:#e8ecf4}
  .section{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:500;letter-spacing:1.5px;text-transform:uppercase;color:#6b7280;margin:24px 0 12px 4px}
  .live-metrics{font-family:'JetBrains Mono',monospace;font-size:12px;color:#c8cdd8;background:#13161f;border:1px solid #252a3a;border-radius:8px;padding:16px;white-space:pre-wrap;max-height:500px;overflow:auto;line-height:1.6}
  .refresh-btn{background:none;border:1px solid #252a3a;color:#6b7280;padding:6px 14px;border-radius:6px;cursor:pointer;font-family:'JetBrains Mono',monospace;font-size:11px;margin-left:12px}
  .refresh-btn:hover{border-color:#3a4060;color:#e8ecf4}
  .heatmap{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
  .heat-chip{padding:4px 10px;border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:11px;border:1px solid #252a3a}
</style>
</head>
<body>
<div class="wrap">
  <a class="back" href="/">&#8592; Back to Monster Forge</a>
  <h1>&#128202; Admin Dashboard</h1>
  <p class="sub">nimble monster forge — observability</p>

  <div class="grid" id="cards">
    <div class="card"><div class="card-title">Total Generations</div><div class="card-value" id="v-gens">—</div></div>
    <div class="card"><div class="card-title">Total Cost</div><div class="card-value accent" id="v-cost">—</div></div>
    <div class="card"><div class="card-title">Active Sessions</div><div class="card-value green" id="v-sessions">—</div></div>
    <div class="card"><div class="card-title">Total Requests</div><div class="card-value blue" id="v-requests">—</div></div>
    <div class="card"><div class="card-title">Input Tokens</div><div class="card-value" id="v-intokens">—</div></div>
    <div class="card"><div class="card-title">Output Tokens</div><div class="card-value" id="v-outtokens">—</div></div>
  </div>

  <div class="section">Monster Options Heatmap</div>
  <div id="heatmap-container" class="card" style="min-height:60px">Loading...</div>

  GRAFANA_EMBED_PLACEHOLDER

  <div class="section">
    Live Prometheus Metrics
    <button class="refresh-btn" onclick="loadMetrics()">Refresh</button>
  </div>
  <div class="live-metrics" id="raw-metrics">Loading...</div>
</div>

<script>
async function loadMetrics() {
  try {
    const res = await fetch('/metrics');
    const text = await res.text();
    document.getElementById('raw-metrics').textContent = text;

    const get = (name, labels) => {
      const pattern = labels
        ? new RegExp('^' + name + '\\{' + labels + '\\}\\s+([\\d.e+-]+)', 'm')
        : new RegExp('^' + name + '\\s+([\\d.e+-]+)', 'm');
      const match = text.match(pattern);
      return match ? parseFloat(match[1]) : 0;
    };

    const sumAll = (name) => {
      const re = new RegExp('^' + name + '(?:_total|_created)?(?:\\{[^}]*\\})?\\s+([\\d.e+-]+)', 'gm');
      let total = 0, m;
      while ((m = re.exec(text)) !== null) total += parseFloat(m[1]);
      return total;
    };

    // Generations
    const gens = get('forge_generation_total', '[^}]*legendary="true"[^}]*')
              + get('forge_generation_total', '[^}]*legendary="false"[^}]*');
    document.getElementById('v-gens').textContent = gens;

    // Cost
    const cost = get('forge_anthropic_cost_dollars_total') || get('forge_anthropic_cost_dollars');
    document.getElementById('v-cost').textContent = '$' + cost.toFixed(4);

    // Sessions
    document.getElementById('v-sessions').textContent = get('forge_active_sessions');

    // Total requests
    const reqRe = /^forge_requests_total\{[^}]*\}\s+([\d.e+-]+)/gm;
    let totalReqs = 0, rm;
    while ((rm = reqRe.exec(text)) !== null) totalReqs += parseFloat(rm[1]);
    document.getElementById('v-requests').textContent = totalReqs;

    // Tokens
    document.getElementById('v-intokens').textContent =
      get('forge_anthropic_tokens_total', '[^}]*direction="input"[^}]*').toLocaleString();
    document.getElementById('v-outtokens').textContent =
      get('forge_anthropic_tokens_total', '[^}]*direction="output"[^}]*').toLocaleString();

    // Heatmap — parse forge_monster_options lines
    const heatRe = /^forge_monster_options_total\{option_type="([^"]+)",option_value="([^"]+)"\}\s+([\d.e+-]+)/gm;
    const options = {};
    let hm;
    while ((hm = heatRe.exec(text)) !== null) {
      const type = hm[1], value = hm[2], count = parseFloat(hm[3]);
      if (count > 0) {
        if (!options[type]) options[type] = [];
        options[type].push({ value, count });
      }
    }

    let heatHtml = '';
    const maxCount = Math.max(1, ...Object.values(options).flatMap(arr => arr.map(o => o.count)));
    for (const [type, vals] of Object.entries(options).sort()) {
      vals.sort((a, b) => b.count - a.count);
      heatHtml += '<div style="margin-bottom:12px"><div style="font-size:12px;color:#6b7280;margin-bottom:6px;text-transform:uppercase;letter-spacing:1px">' + type + '</div><div class="heatmap">';
      for (const { value, count } of vals) {
        const intensity = Math.round((count / maxCount) * 255);
        const bg = 'rgba(' + intensity + ',' + Math.round(intensity * 0.65) + ',20,0.3)';
        const border = 'rgba(' + intensity + ',' + Math.round(intensity * 0.65) + ',20,0.6)';
        heatHtml += '<span class="heat-chip" style="background:' + bg + ';border-color:' + border + ';color:rgb(' + Math.min(255, intensity + 80) + ',' + Math.min(255, Math.round(intensity * 0.65) + 60) + ',40)">' + value + ' <b>' + count + '</b></span>';
      }
      heatHtml += '</div></div>';
    }
    document.getElementById('heatmap-container').innerHTML = heatHtml || '<span style="color:#6b7280">No monster generations yet</span>';

  } catch(e) {
    document.getElementById('raw-metrics').textContent = 'Error: ' + e.message;
  }
}

loadMetrics();
setInterval(loadMetrics, 15000);
</script>
</body></html>"""


# ── Configuration ─────────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 8000))


# ── Frontend HTML ─────────────────────────────────────────────────────────
# Only change from original: generate() now sends an `options` object
# alongside the prompt so the server can track feature selections.

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nimble Monster Forge</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#0f0c07;color:#e8d5b0;font-family:'Crimson Text','Palatino Linotype',serif;min-height:100vh;padding:24px}
  .wrap{max-width:720px;margin:0 auto}
  h1{font-family:'Cinzel',serif;font-size:26px;color:#d4a832;letter-spacing:3px}
  .sub{color:#8a7a5a;font-size:14px;font-style:italic;margin-bottom:28px}
  label.section{color:#a89060;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;display:block;margin-bottom:6px}
  input,select,textarea{background:#2a2418;border:1px solid #5a4a2e;border-radius:4px;color:#e8d5b0;padding:8px 12px;font-size:14px;font-family:'Crimson Text',serif;outline:none;width:100%}
  input:focus,select:focus,textarea:focus{border-color:#8b6914}
  textarea{resize:vertical;min-height:56px}
  .row{display:flex;gap:8px;margin-bottom:6px}.row input{flex:1}.row select{flex:1;cursor:pointer}.row .lvl{width:56px;text-align:center;flex:none}
  .btn-rm{background:none;border:1px solid #5a3a2e;color:#a05a3a;border-radius:4px;width:32px;cursor:pointer;font-size:16px}
  .btn-add{background:none;border:1px dashed #5a4a2e;color:#8a7a5a;padding:5px 14px;border-radius:4px;cursor:pointer;font-size:12px;font-family:'Crimson Text',serif}
  .chips{display:flex;flex-wrap:wrap;gap:4px}
  .chip{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;cursor:pointer;border:1px solid #5a4a2e;color:#8a7a5a;user-select:none;transition:all .15s}
  .chip.on{border-color:#d4a832;background:#3a2f1e;color:#d4a832}
  .group{margin-bottom:18px}
  .btn-forge{width:100%;padding:14px;font-size:16px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;font-family:'Cinzel',serif;background:linear-gradient(135deg,#8b6914,#d4a832,#8b6914);color:#1a1207;border:none;border-radius:4px;cursor:pointer}
  .btn-forge:disabled{background:#2a2418;color:#8a7a5a;cursor:wait}
  .error{margin-top:16px;padding:12px;background:#3a1a1a;border:1px solid #8a3a3a;border-radius:4px;color:#e88;font-size:13px;white-space:pre-wrap;word-break:break-all;max-height:200px;overflow:auto}
  .stat-block{background:linear-gradient(135deg,#1a1207 0%,#2a1f10 50%,#1a1207 100%);border:2px solid #8b6914;border-radius:2px;padding:20px;position:relative;margin-top:28px;overflow:hidden}
  .bar{height:3px;background:linear-gradient(90deg,transparent,#8b6914,#d4a832,#8b6914,transparent);position:absolute;left:0;right:0}.bar.top{top:0}.bar.bot{bottom:0}
  .divider{height:1px;background:linear-gradient(90deg,transparent,#8b6914,transparent);margin:10px 0}
  .gold{color:#d4a832}.muted{color:#a89060}.dim{color:#8a7a5a}
  .stat-name{font-family:'Cinzel',serif;font-size:22px;color:#d4a832;font-weight:700}
  .hp-box{font-size:28px;font-weight:bold;color:#d4a832}
  .armor-badge{background:#8b6914;color:#1a1207;padding:1px 8px;border-radius:2px;font-size:13px;font-weight:bold}
  .red{color:#c44;font-weight:bold;text-transform:uppercase;letter-spacing:1px;font-size:13px}
  .actions{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
  .btn-at{padding:10px 20px;border-radius:4px;cursor:pointer;font-size:14px;font-weight:bold;font-family:'Cinzel',serif;border:2px solid #3a6a3a;background:#1a2a1e;color:#6cb86c}
  .btn-at.saving{background:#2a2418;color:#8a7a5a;border-color:#5a4a2e;cursor:wait}
  .btn-at.saved{background:#1a2a1a;color:#8f8;border-color:#4a8a2e}
  .btn-at.err{background:#3a1a1a;color:#e88;border-color:#8a3a3a}
  .btn-exp{padding:8px 14px;border-radius:4px;cursor:pointer;font-size:13px;font-family:'Crimson Text',serif;border:1px solid #8b6914;background:#3a2f1e;color:#d4a832}
  .btn-exp.on{background:#2d5a1e;color:#8f8;border-color:#4a8a2e}
  .export-area{width:100%;min-height:140px;max-height:400px;background:#1a1207;border:1px solid #5a4a2e;border-radius:4px;color:#e8d5b0;padding:12px;font-size:13px;font-family:monospace;resize:vertical;outline:none;margin-top:10px}
  .config-panel{background:#1a1207;border:1px solid #5a4a2e;border-radius:6px;padding:20px;margin-bottom:20px}
  .config-panel input{font-family:monospace}
  .hint{font-size:11px;color:#8a7a5a;margin-top:4px}
  .btn-cfg{background:none;border:1px solid #5a4a2e;color:#8a7a5a;padding:4px 12px;border-radius:4px;cursor:pointer;font-size:12px;font-family:'Crimson Text',serif}
  .btn-cfg.on{border-color:#3a6a3a;color:#6cb86c}
  .btn-save-cfg{background:linear-gradient(135deg,#8b6914,#d4a832);color:#1a1207;border:none;padding:8px 20px;border-radius:4px;cursor:pointer;font-size:13px;font-weight:bold;font-family:'Cinzel',serif}
  .btn-cancel{background:none;color:#8a7a5a;border:1px solid #5a4a2e;padding:8px 20px;border-radius:4px;cursor:pointer;font-size:13px}
  .top-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
  .opts-row{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-end;margin-bottom:18px}.opts-row>div{flex:1;min-width:130px}
  .cb-label{display:flex;align-items:center;gap:8px;cursor:pointer;padding-bottom:8px;font-size:14px}
  .status{margin-top:8px;font-size:13px}.status.ok{color:#6cb86c}.status.err{color:#e88}
</style>
</head>
<body>
<div class="wrap" id="app"></div>
<script>
const CLASSES=["Berserker","Cheat","Commander","Hunter","Mage","Oathsworn","Shadowmancer","Shepherd","Songweaver","Stormshifter","Zephyr"];
const THEMES=["cosmic horror","sword-and-sorcery","dark fairy tale","wilderness","undead","elemental","beast hunt","cult","ancient ruins","pirate","swamp","desert"];
const ENVS=["forest","underground","hill","field","dungeon","marsh","desert","mountain","sky","urban","shadowblight","coastal"];

const SYSTEM_PROMPT=`You are a Nimble RPG monster designer. Create mechanically valid monsters for Nimble v2.0.3.

IMPORTANT OUTPUT RULES:
- Respond with ONLY valid JSON. No markdown, no backticks, no commentary.
- NEVER use double quotes inside string values. Use single quotes instead.
- Keep all string values on a single line. No line breaks inside strings.

MONSTER STAT TABLE (Level | HP None/M/H | DPR | Dice | Save DC):
0.25|12/9/7|3|1d4+1|9  0.33|15/11/8|5|1d6+2|9  0.5|18/15/11|7|1d6+3|10
1|26/20/16|11|2d8+2|10  2|34/27/20|13|2d8+4|11  3|41/33/25|15|2d8+6|11
4|49/39/29|18|2d8+9|12  5|58/46/35|19|2d8+10|12  6|68/54/41|21|2d8+12|13
7|79/63/47|24|3d8+10|13  8|91/73/55|26|3d8+12|14  9|104/83/62|28|4d8+10|14
10|118/94/71|30|4d8+12|15  11|133/106/80|33|5d8+11|15  12|149/119/89|35|5d8+13|16
13|166/132/100|38|6d8+11|16  14|184/147/110|40|6d8+13|17  15|203/162/122|43|7d8+11|17
16|223/178/134|45|7d8+13|18  17|244/195/146|48|8d8+12|18  18|266/213/160|50|8d8+14|19
19|289/231/173|52|9d8+12|19  20|313/250/189|54|9d8+13|20

LEGENDARY TABLE (Party Lvl | HP M/H | Last Stand HP | DC | Small/Big Dmg):
1|50/35|10|10|8/16  2|75/55|20|11|9/18  3|100/75|30|11|10/20  4|125/95|40|12|11/22
5|150/115|50|12|12/24  6|175/135|60|13|13/26  7|200/155|70|13|14/28  8|225/175|80|14|15/30
9|250/195|90|14|16/32  10|275/215|100|15|17/34  12|325/255|120|16|19/38  14|375/295|140|17|21/42
16|425/335|160|18|23/46  18|475/375|180|19|25/50  20|525/415|200|20|27/54

RULES:
- For each special ability, lower HP or damage by 1 row. State which tradeoff.
- Die themes: d4 undead, d6 goblins/small, d8 humans, d10 beasts, d12 giants, d20 mightiest
- Encounter balance: monster levels = hero levels is Hard. 75% is Medium. <50% Easy. 125% Deadly.
- Unarmored: normal damage. Medium(M): dice only, ignore modifiers. Heavy(H): half dice, ignore modifiers.
- Legendary monsters act after EACH hero turn, have Bloodied at half HP, Last Stand at 0 HP.

JSON SCHEMA (respond with EXACTLY this structure):
{"name":"","level":0,"hp":0,"armor":"None","speed":6,"fly":null,"burrow":null,"size":"Medium","dpr":0,"save_dc":0,"attacks":"Attack1. dice+mod. Effect. | Attack2. dice+mod.","trait":"Trait Name. Description.","abilities":"Ability1. Description. | Ability2. Description.","legendary":false,"bloodied":"","last_stand":"","last_stand_hp":null,"saves":"","lore":"","tips":"","encounter":"","balance":"","tags":"tag1, tag2","family":""}`;

let state={heroes:[{name:"",cls:"Berserker",level:3}],theme:[],env:[],diff:"Hard",legendary:false,custom:"",size:"",loading:false,error:null,monster:null,showExport:null,showConfig:false,cfg:JSON.parse(localStorage.getItem("nimble_cfg")||'{"anthropicKey":"","inviteCode":"","atToken":"","atBase":"","atTable":""}'),atStatus:null,atError:null,atWarnings:null};

function saveCfg(){localStorage.setItem("nimble_cfg",JSON.stringify(state.cfg))}
function totalLvl(){return state.heroes.reduce((s,h)=>s+(parseInt(h.level)||1),0)}
function avgLvl(){return Math.round(totalLvl()/state.heroes.length)}
function hasCfg(){return !!(state.cfg.anthropicKey||state.cfg.inviteCode)}
function hasAt(){return state.cfg.atToken&&state.cfg.atBase&&state.cfg.atTable}

function parseResponse(text){
  let s=text.replace(/```json\s?|```/g,"").trim();
  let a=s.indexOf("{"),b=s.lastIndexOf("}");
  if(a===-1||b===-1)throw new Error("No JSON in response");
  s=s.slice(a,b+1).replace(/[\x00-\x1f]/g,ch=>(ch==="\n"||ch==="\r"||ch==="\t")?" ":"");
  return JSON.parse(s);
}

function toFields(m){
  let f={};const set=(k,v)=>{if(v!==null&&v!==undefined&&v!=="")f[k]=v};
  set("Name",m.name||"Unnamed");set("Level",m.level);set("HP",m.hp);
  var armorVal=String(m.armor||"None");if(armorVal.toLowerCase().includes("heavy")||armorVal.includes("H"))armorVal="Heavy";else if(armorVal.toLowerCase().includes("med")||armorVal.includes("M"))armorVal="Medium";else armorVal="None";
  set("Armor Type",armorVal);set("Speed",m.speed||6);
  set("Fly Speed",m.fly);set("Burrow Speed",m.burrow);
  set("Size",m.size||"Medium");set("Damage Per Round",m.dpr);
  set("Save DC",m.save_dc);
  set("Attack Description",(m.attacks||"").replace(/\|/g,"\n").trim());
  set("Special Abilities",[m.trait,m.abilities].filter(Boolean).join("\n"));
  set("Monster Family",m.family||"Homebrew");
  if(m.tags){f["Environment Tags"]=m.tags}
  set("Is Legendary",m.legendary||false);
  set("Bloodied Ability",m.bloodied);set("Last Stand Ability",m.last_stand);
  set("Last Stand HP",m.last_stand_hp);set("Advantaged Saves",m.saves);
  set("Source","AI Generated");
  set("Notes",[m.lore,m.tips?"GM: "+m.tips:null,m.encounter?"Encounter: "+m.encounter:null,m.balance?"Balance: "+m.balance:null].filter(Boolean).join("\n\n"));
  return f;
}

async function generate(){
  state.loading=true;state.error=null;state.monster=null;state.atStatus=null;state.atWarnings=null;state.showExport=null;render();
  if(!state.cfg.anthropicKey&&!state.cfg.inviteCode){state.loading=false;state.error="Enter an invite code or Anthropic API key in Settings.";state.showConfig=true;render();return}
  const party=state.heroes.map((h,i)=>`${h.name||"Hero "+(i+1)}: Level ${h.level} ${h.cls}`).join(", ");
  const prompt=`Create a ${state.legendary?"LEGENDARY ":""}monster for: ${party} (${state.heroes.length} heroes, total levels ${totalLvl()}). Difficulty: ${state.diff}. Theme: ${state.theme.join(", ")||"any"}. Environment: ${state.env.join(", ")||"any"}. ${state.size?"Size: "+state.size+".":""} ${state.legendary?"Use Legendary table at party level "+avgLvl()+".":""} ${state.custom}`;

  // Send structured options alongside prompt for server-side metrics
  const options = {
    themes: state.theme,
    environments: state.env,
    difficulty: state.diff,
    legendary: state.legendary,
    size: state.size || "Any",
    party_size: state.heroes.length,
    classes: state.heroes.map(h => h.cls)
  };

  // Send either API key or invite code (invite code takes priority)
  const payload = {system:SYSTEM_PROMPT,prompt:prompt,options:options};
  if(state.cfg.inviteCode){payload.inviteCode=state.cfg.inviteCode}
  else{payload.key=state.cfg.anthropicKey}

  try{
    const res=await fetch("/api/claude",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(payload)
    });
    const data=await res.json();
    if(data.error)throw new Error(data.error);
    state.monster=parseResponse(data.text);
  }catch(e){state.error=e.message}
  state.loading=false;render();
  if(state.monster)document.getElementById("result")?.scrollIntoView({behavior:"smooth"});
}

async function saveToAirtable(){
  if(!hasAt()){state.showConfig=true;render();return}
  state.atStatus="saving";state.atError=null;state.atWarnings=null;render();
  try{
    var fields=toFields(state.monster);
    const res=await fetch("/api/airtable",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({token:state.cfg.atToken,baseId:state.cfg.atBase,tableId:state.cfg.atTable,fields:fields})
    });
    const data=await res.json();
    if(data.error)throw new Error(data.error);
    state.atStatus="saved";
    if(data.warnings&&data.warnings.length>0){state.atWarnings=data.warnings}
  }catch(e){state.atStatus="error";state.atError=e.message}
  render();
}

function esc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}

function render(){
  const m=state.monster;const app=document.getElementById("app");
  function chips(list,sel,fn){return list.map(v=>`<span class="chip ${sel.includes(v)?'on':''}" onclick="${fn}('${v}')">${v}</span>`).join("")}
  function rchips(list,cur,fn){return list.map(v=>`<span class="chip ${cur===v?'on':''}" onclick="${fn}('${v}')">${v}</span>`).join("")}

  let h=`<div class="top-bar"><h1>&#9876; NIMBLE MONSTER FORGE</h1>
    <button class="btn-cfg ${hasCfg()?'on':''}" onclick="state.showConfig=!state.showConfig;render()">${hasCfg()?"&#9679; Settings":"&#9881; Settings"}</button></div>
    <p class="sub">AI-powered creature design for Nimble RPG</p>`;

  if(state.showConfig){const c=state.cfg;
    h+=`<div class="config-panel"><span class="gold" style="font-family:Cinzel,serif;font-size:14px;font-weight:bold;letter-spacing:1px">API SETTINGS</span>
    <div style="margin-top:16px;margin-bottom:12px"><label class="section">Invite Code</label>
    <input id="cfgInv" value="${esc(c.inviteCode||"")}" placeholder="Enter invite code..."><div class="hint">Have an invite code? Enter it here — no API key needed</div></div>
    <div class="divider"></div>
    <div style="margin-bottom:12px;margin-top:12px"><label class="section">Anthropic API Key <span class="dim">(or use invite code above)</span></label>
    <input type="password" id="cfgA" value="${esc(c.anthropicKey)}" placeholder="sk-ant-..."><div class="hint">console.anthropic.com/settings/keys</div></div>
    <div style="margin-bottom:12px"><label class="section">Airtable Token</label>
    <input type="password" id="cfgT" value="${esc(c.atToken)}" placeholder="pat..."><div class="hint">airtable.com/create/tokens — needs data.records:write</div></div>
    <div style="margin-bottom:12px"><label class="section">Airtable Base ID</label>
    <input id="cfgB" value="${esc(c.atBase)}" placeholder="appXXXXXXXXXXXXXX"></div>
    <div style="margin-bottom:16px"><label class="section">Airtable Monsters Table ID</label>
    <input id="cfgTbl" value="${esc(c.atTable)}" placeholder="tblXXXXXXXXXXXXXX"><div class="hint">Both IDs from your URL: airtable.com/appXXX/tblXXX/...</div></div>
    <div style="display:flex;gap:8px"><button class="btn-save-cfg" onclick="state.cfg={anthropicKey:document.getElementById('cfgA').value,inviteCode:document.getElementById('cfgInv').value,atToken:document.getElementById('cfgT').value,atBase:document.getElementById('cfgB').value,atTable:document.getElementById('cfgTbl').value};saveCfg();state.showConfig=false;render()">Save</button>
    <button class="btn-cancel" onclick="state.showConfig=false;render()">Cancel</button></div></div>`}

  h+=`<div class="group"><div style="display:flex;justify-content:space-between;margin-bottom:8px">
    <label class="section" style="margin:0">Your Party</label>
    <span class="dim" style="font-size:13px">Total Levels: <b class="gold">${totalLvl()}</b></span></div>`;
  state.heroes.forEach((hr,i)=>{const opts=CLASSES.map(c=>`<option ${c===hr.cls?"selected":""}>${c}</option>`).join("");
    h+=`<div class="row"><input placeholder="Name" value="${esc(hr.name)}" oninput="state.heroes[${i}].name=this.value">
    <select onchange="state.heroes[${i}].cls=this.value">${opts}</select>
    <input class="lvl" type="number" min="1" max="20" value="${hr.level}" onchange="state.heroes[${i}].level=parseInt(this.value)||1">
    ${state.heroes.length>1?`<button class="btn-rm" onclick="state.heroes.splice(${i},1);render()">&#215;</button>`:""}</div>`});
  h+=`<button class="btn-add" onclick="state.heroes.push({name:'',cls:'Berserker',level:${avgLvl()||1}});render()">+ Add Hero</button></div>`;

  h+=`<div class="group"><label class="section">Difficulty</label><div class="chips">${rchips(["Easy","Medium","Hard","Deadly","Very Deadly"],state.diff,"setDiff")}</div></div>`;
  h+=`<div class="group"><label class="section">Theme</label><div class="chips">${chips(THEMES,state.theme,"toggleTheme")}</div></div>`;
  h+=`<div class="group"><label class="section">Environment</label><div class="chips">${chips(ENVS,state.env,"toggleEnv")}</div></div>`;

  const sOpts=["","Tiny","Small","Medium","Large","Huge","Gargantuan"].map(s=>`<option ${s===state.size?"selected":""} value="${s}">${s||"Any"}</option>`).join("");
  h+=`<div class="opts-row"><div><label class="section">Size</label><select onchange="state.size=this.value">${sOpts}</select></div>
  <label class="cb-label" style="color:${state.legendary?'#d4a832':'#8a7a5a'}"><input type="checkbox" ${state.legendary?"checked":""} onchange="state.legendary=this.checked;render()" style="accent-color:#d4a832"> Legendary</label></div>`;

  h+=`<div class="group"><label class="section">Custom Instructions</label><textarea placeholder="e.g. 'A corrupted treant' or 'punishes ranged attackers'" oninput="state.custom=this.value">${esc(state.custom)}</textarea></div>`;
  h+=`<button class="btn-forge" ${state.loading?"disabled":""} onclick="generate()">${state.loading?"Forging...":"&#9874; Forge Monster"}</button>`;
  if(state.error)h+=`<div class="error">${esc(state.error)}</div>`;

  if(m){
    const spd=[m.speed,m.fly&&("Fly "+m.fly),m.burrow&&("Burrow "+m.burrow)].filter(Boolean).join(", ");
    const ab=m.armor!=="None"?(m.armor.includes("H")?"H":m.armor.includes("M")?"M":""):"";
    const attacks=(m.attacks||"").split("|").map(s=>s.trim()).filter(Boolean);
    const abilities=(m.abilities||"").split("|").map(s=>s.trim()).filter(Boolean);

    h+=`<div class="stat-block" id="result"><div class="bar top"></div>
    <div style="display:flex;justify-content:space-between;align-items:flex-start"><div>
    <div class="stat-name">${esc(m.name)}</div>
    <div class="muted" style="font-size:12px;margin-top:4px">Lvl ${m.level} &#8226; ${m.size} &#8226; ${m.armor==="None"?"Unarmored":m.armor} &#8226; Speed ${spd} &#8226; DC ${m.save_dc}${m.legendary?" &#8226; LEGENDARY":""}</div></div>
    <div style="display:flex;align-items:center;gap:6px">${ab?`<span class="armor-badge">${ab}</span>`:""}<span class="hp-box">${m.hp}</span></div></div><div class="divider"></div>`;

    if(m.trait){const p=m.trait.split(".");h+=`<div style="margin-bottom:8px;font-size:14px"><span class="gold" style="font-weight:600">${esc(p[0])}.</span> ${esc(p.slice(1).join(".").trim())}</div>`}
    abilities.forEach(a=>{const p=a.split(".");h+=`<div style="margin-bottom:6px;font-size:14px"><span class="gold" style="font-weight:600">${esc(p[0])}.</span> ${esc(p.slice(1).join(".").trim())}</div>`});
    attacks.forEach(a=>{const p=a.split(".");h+=`<div style="margin-bottom:5px;font-size:14px"><b>&#8226; ${esc(p[0])}.</b> ${esc(p.slice(1).join(".").trim())}</div>`});
    if(m.legendary&&m.bloodied)h+=`<div class="divider"></div><div style="margin-bottom:6px;font-size:14px"><span class="red">Bloodied: </span>${esc(m.bloodied)}</div>`;
    if(m.legendary&&m.last_stand)h+=`<div style="margin-bottom:6px;font-size:14px"><span class="red">Last Stand: </span>${esc(m.last_stand)}${m.last_stand_hp?" ("+m.last_stand_hp+" more HP to kill.)":""}</div>`;
    if(m.saves)h+=`<div class="muted" style="font-size:12px;margin-top:6px">Saves: ${esc(m.saves)}</div>`;
    h+=`<div class="divider"></div><div class="muted" style="font-size:13px;font-style:italic">${esc(m.lore||"")}</div>`;
    if(m.tips)h+=`<div class="dim" style="font-size:13px;margin-top:6px"><b class="muted">GM:</b> ${esc(m.tips)}</div>`;
    if(m.encounter)h+=`<div class="dim" style="font-size:13px;margin-top:4px"><b class="muted">Encounter:</b> ${esc(m.encounter)}</div>`;
    if(m.balance)h+=`<div class="dim" style="font-size:13px;margin-top:4px"><b class="muted">Balance:</b> ${esc(m.balance)}</div>`;
    h+=`<div class="bar bot"></div></div>`;

    const atCls=state.atStatus==="saving"?"saving":state.atStatus==="saved"?"saved":state.atStatus==="error"?"err":"";
    const atLbl=state.atStatus==="saving"?"Saving...":state.atStatus==="saved"?"&#10003; Saved!":state.atStatus==="error"?"&#10007; Retry":"Save to Airtable";
    h+=`<div class="actions"><button class="btn-at ${atCls}" onclick="saveToAirtable()" ${state.atStatus==="saving"?"disabled":""}>${atLbl}</button>
    <button class="btn-exp ${state.showExport==="statblock"?"on":""}" onclick="state.showExport=state.showExport==='statblock'?null:'statblock';render()">${state.showExport==="statblock"?"&#9662;":"&#9656;"} Stat Block</button>
    <button class="btn-exp ${state.showExport==="json"?"on":""}" onclick="state.showExport=state.showExport==='json'?null:'json';render()">${state.showExport==="json"?"&#9662;":"&#9656;"} JSON</button></div>`;

    if(state.atStatus==="saved"&&!state.atWarnings)h+=`<div class="status ok">Record created in your Monsters table!</div>`;
    if(state.atStatus==="saved"&&state.atWarnings&&state.atWarnings.length>0)h+=`<div class="status" style="color:#d4a832">&#9888; Saved with ${state.atWarnings.length} field(s) dropped (logged in Notes):<br><span class="dim" style="font-size:12px">${esc(state.atWarnings.join(" | "))}</span></div>`;
    if(state.atStatus==="error")h+=`<div class="status err">${esc(state.atError||"Unknown error")}</div>`;

    if(state.showExport){let txt="";
      if(state.showExport==="statblock")txt=[m.name+" — Lvl "+m.level+(m.size!=="Medium"?", "+m.size:""),m.trait,m.abilities,(m.attacks||"").split("|").map(a=>"• "+a.trim()).join("\n"),m.legendary&&m.bloodied?"BLOODIED: "+m.bloodied:null,m.legendary&&m.last_stand?"LAST STAND: "+m.last_stand:null,m.hp+(m.armor!=="None"?" "+m.armor:"")].filter(Boolean).join("\n");
      else txt=JSON.stringify(m,null,2);
      h+=`<div style="margin-top:10px"><div class="dim" style="font-size:12px;margin-bottom:4px">Select all + copy:</div><textarea class="export-area" readonly onfocus="this.select()">${esc(txt)}</textarea></div>`}
  }
  app.innerHTML=h;
}

window.setDiff=v=>{state.diff=v;render()};
window.toggleTheme=v=>{state.theme=state.theme.includes(v)?state.theme.filter(x=>x!==v):[...state.theme,v];render()};
window.toggleEnv=v=>{state.env=state.env.includes(v)?state.env.filter(x=>x!==v):[...state.env,v];render()};
render();
</script>
</body></html>"""


# ── HTTP Handler ──────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        start = time.time()

        if self.path == "/metrics":
            # ── Prometheus metrics endpoint (protected by bearer token) ──
            if METRICS_BEARER_TOKEN:
                auth_header = self.headers.get("Authorization", "")
                expected = f"Bearer {METRICS_BEARER_TOKEN}"
                if auth_header != expected:
                    self.send_response(401)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"401 Unauthorized - Bearer token required")
                    return
            metrics_data = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(metrics_data)
            return

        if self.path == "/admin":
            if not self._check_admin_auth():
                return
            admin_page = ADMIN_HTML
            if GRAFANA_DASHBOARD_URL:
                embed_html = (
                    '<div class="section">Grafana Dashboard</div>'
                    f'<iframe class="grafana-frame" src="{GRAFANA_DASHBOARD_URL}" frameborder="0"></iframe>'
                )
            else:
                embed_html = (
                    '<div class="hint">'
                    '<strong>Grafana embeds not configured yet.</strong><br><br>'
                    'Set GRAFANA_DASHBOARD_URL env var to your Grafana Cloud panel embed URL.<br>'
                    'The live metrics below are pulled directly from /metrics.'
                    '</div>'
                )
            admin_page = admin_page.replace("GRAFANA_EMBED_PLACEHOLDER", embed_html)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(admin_page.encode())
            _track_session(self.client_address[0])
            REQUESTS_TOTAL.labels(endpoint="/admin", method="GET", status="200").inc()
            REQUEST_DURATION.labels(endpoint="/admin").observe(time.time() - start)
            return

        if self.path == "/health":
            self._json_response(200, {"status": "ok", "uptime": time.time() - SERVER_START})
            return

        # Serve frontend
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(HTML.encode())
        _track_session(self.client_address[0])
        REQUESTS_TOTAL.labels(endpoint="/", method="GET", status="200").inc()
        REQUEST_DURATION.labels(endpoint="/").observe(time.time() - start)

    def do_POST(self):
        start = time.time()
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        _track_session(self.client_address[0])

        if self.path == "/api/claude":
            self._proxy_claude(body, start)
        elif self.path == "/api/airtable":
            self._proxy_airtable(body, start)
        else:
            self._json_response(404, {"error": "Not found"})
            REQUESTS_TOTAL.labels(endpoint=self.path, method="POST", status="404").inc()

    def _check_admin_auth(self):
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode()
                _, password = decoded.split(":", 1)
                if password == ADMIN_KEY:
                    return True
            except Exception:
                pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Nimble Forge Admin"')
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>401 Unauthorized</h1><p>Admin access required.</p>")
        return False

    def _proxy_claude(self, body, start):
        options = body.get("options", {})

        # ── Resolve API key: either user's own key or invite code ──
        api_key = body.get("key", "")
        invite_code = body.get("inviteCode", "").strip()

        if invite_code:
            # Validate invite code
            with _invite_lock:
                if invite_code not in _invite_codes:
                    self._json_response(403, {"error": "Invalid invite code."})
                    return
                max_uses = _invite_codes[invite_code]
                current = _invite_usage.get(invite_code, 0)
                if current >= max_uses:
                    self._json_response(403, {"error": f"Invite code '{invite_code}' has reached its usage limit ({max_uses})."})
                    return
                _invite_usage[invite_code] = current + 1
                INVITE_USAGE.labels(code=invite_code).inc()

            if not ANTHROPIC_API_KEY:
                self._json_response(500, {"error": "Server API key not configured. Contact the admin."})
                return
            api_key = ANTHROPIC_API_KEY
            print(f"  [invite] Code '{invite_code}' used ({_invite_usage[invite_code]}/{_invite_codes[invite_code]})")

        if not api_key:
            self._json_response(400, {"error": "No API key or invite code provided."})
            return

        try:
            payload = json.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "system": body.get("system", ""),
                "messages": [{"role": "user", "content": body.get("prompt", "")}]
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01"
                }
            )
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read())
                text = "".join(b.get("text", "") for b in data.get("content", []))

                # ── Token usage & cost tracking ──
                usage = data.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                ANTHROPIC_TOKENS.labels(direction="input").inc(input_tokens)
                ANTHROPIC_TOKENS.labels(direction="output").inc(output_tokens)
                cost = (input_tokens * INPUT_COST_PER_TOKEN) + (output_tokens * OUTPUT_COST_PER_TOKEN)
                ANTHROPIC_COST.inc(cost)

                # ── Monster options tracking ──
                is_legendary = str(options.get("legendary", False)).lower()
                GENERATION_TOTAL.labels(legendary=is_legendary).inc()
                for theme in options.get("themes", []):
                    MONSTER_OPTIONS.labels(option_type="theme", option_value=theme).inc()
                for env in options.get("environments", []):
                    MONSTER_OPTIONS.labels(option_type="environment", option_value=env).inc()
                if options.get("difficulty"):
                    MONSTER_OPTIONS.labels(option_type="difficulty", option_value=options["difficulty"]).inc()
                if options.get("size"):
                    MONSTER_OPTIONS.labels(option_type="size", option_value=options["size"]).inc()
                for cls in options.get("classes", []):
                    MONSTER_OPTIONS.labels(option_type="class", option_value=cls).inc()
                if options.get("party_size"):
                    MONSTER_OPTIONS.labels(option_type="party_size", option_value=str(options["party_size"])).inc()

                self._json_response(200, {"text": text})
                REQUESTS_TOTAL.labels(endpoint="/api/claude", method="POST", status="200").inc()
                REQUEST_DURATION.labels(endpoint="/api/claude").observe(time.time() - start)
                print(f"  [metrics] Generation: {input_tokens} in / {output_tokens} out = ${cost:.4f}")

        except urllib.error.HTTPError as e:
            err = e.read().decode()
            try:
                msg = json.loads(err).get("error", {}).get("message", err)
            except Exception:
                msg = err
            self._json_response(e.code, {"error": msg})
            REQUESTS_TOTAL.labels(endpoint="/api/claude", method="POST", status=str(e.code)).inc()
            ERRORS_TOTAL.labels(error_type="anthropic_http", endpoint="/api/claude").inc()
            REQUEST_DURATION.labels(endpoint="/api/claude").observe(time.time() - start)
        except Exception as e:
            self._json_response(500, {"error": str(e)})
            REQUESTS_TOTAL.labels(endpoint="/api/claude", method="POST", status="500").inc()
            ERRORS_TOTAL.labels(error_type="anthropic_exception", endpoint="/api/claude").inc()
            REQUEST_DURATION.labels(endpoint="/api/claude").observe(time.time() - start)

    def _proxy_airtable(self, body, start):
        url = f"https://api.airtable.com/v0/{body['baseId']}/{body['tableId']}"
        token = body.get("token", "")
        fields = dict(body.get("fields", {}))
        errors_log = []
        max_retries = 5

        for attempt in range(max_retries):
            try:
                payload = json.dumps({"records": [{"fields": fields}]}).encode()
                req = urllib.request.Request(
                    url, data=payload,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req) as res:
                    data = json.loads(res.read())
                    record_id = data.get("records", [{}])[0].get("id")
                    self._json_response(200, {"ok": True, "id": record_id, "warnings": errors_log})
                    AIRTABLE_SAVES.labels(status="success").inc()
                    REQUESTS_TOTAL.labels(endpoint="/api/airtable", method="POST", status="200").inc()
                    REQUEST_DURATION.labels(endpoint="/api/airtable").observe(time.time() - start)
                    return
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                try:
                    err_msg = json.loads(err_body).get("error", {}).get("message", err_body)
                except Exception:
                    err_msg = err_body

                problem_field = None
                m = re.search(r'Unknown field name:\s*"([^"]+)"', err_msg)
                if m:
                    problem_field = m.group(1)
                if not problem_field:
                    m = re.search(r'Cannot parse value for field\s+(\w[\w\s]*\w|\w+)', err_msg)
                    if m:
                        problem_field = m.group(1).strip()
                if not problem_field:
                    m = re.search(r'[Ff]ield\s+"([^"]+)"', err_msg)
                    if m:
                        problem_field = m.group(1)

                if problem_field and problem_field in fields:
                    failed_value = fields.pop(problem_field)
                    errors_log.append(f"{problem_field}: {failed_value}")
                    print(f"  Airtable rejected field '{problem_field}', retrying (attempt {attempt + 1})")
                    notes = fields.get("Notes", "")
                    if notes:
                        notes += "\n\n"
                    notes += "⚠ IMPORT ERRORS:\n" + "\n".join(errors_log)
                    fields["Notes"] = notes
                    continue
                else:
                    self._json_response(e.code, {"error": err_msg})
                    AIRTABLE_SAVES.labels(status="error").inc()
                    ERRORS_TOTAL.labels(error_type="airtable_http", endpoint="/api/airtable").inc()
                    REQUESTS_TOTAL.labels(endpoint="/api/airtable", method="POST", status=str(e.code)).inc()
                    REQUEST_DURATION.labels(endpoint="/api/airtable").observe(time.time() - start)
                    return
            except Exception as e:
                self._json_response(500, {"error": str(e)})
                AIRTABLE_SAVES.labels(status="error").inc()
                ERRORS_TOTAL.labels(error_type="airtable_exception", endpoint="/api/airtable").inc()
                REQUESTS_TOTAL.labels(endpoint="/api/airtable", method="POST", status="500").inc()
                REQUEST_DURATION.labels(endpoint="/api/airtable").observe(time.time() - start)
                return

        self._json_response(500, {"error": f"Too many field errors. Dropped: {', '.join(errors_log)}"})
        AIRTABLE_SAVES.labels(status="error").inc()
        ERRORS_TOTAL.labels(error_type="airtable_retries_exhausted", endpoint="/api/airtable").inc()
        REQUESTS_TOTAL.labels(endpoint="/api/airtable", method="POST", status="500").inc()
        REQUEST_DURATION.labels(endpoint="/api/airtable").observe(time.time() - start)

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        msg = fmt % args
        if any(p in msg for p in ["GET / ", "POST /api", "/admin", "/metrics"]):
            print(f"  {msg}")


# ── Server Startup ────────────────────────────────────────────────────────
SERVER_START = time.time()

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════╗
║       ⚔  NIMBLE MONSTER FORGE  ⚔        ║
║            with Observability            ║
║                                          ║
║  App:     http://localhost:{PORT}           ║
║  Admin:   http://localhost:{PORT}/admin      ║
║  Metrics: http://localhost:{PORT}/metrics    ║
║  Stop:    Ctrl+C                         ║
╚══════════════════════════════════════════╝
""")

    if METRICS_BEARER_TOKEN:
        print("  [metrics] /metrics endpoint protected by bearer token")
        print("  [metrics] Configure Grafana Cloud Metrics Endpoint integration to scrape it")
    else:
        print("  [metrics] /metrics endpoint is open (set METRICS_BEARER_TOKEN to protect it)")

    if _invite_codes:
        print(f"  [invite] {len(_invite_codes)} invite code(s) active: {', '.join(f'{k}:{v}' for k,v in _invite_codes.items())}")
        if ANTHROPIC_API_KEY:
            print("  [invite] Server-side API key configured")
        else:
            print("  [invite] WARNING: ANTHROPIC_API_KEY not set — invite codes won't work!")
    else:
        print("  [invite] No invite codes configured (set INVITE_CODES env var)")
    print()

    server = http.server.HTTPServer(("", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
