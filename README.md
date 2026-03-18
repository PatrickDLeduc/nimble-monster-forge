# ⚔ Nimble Monster Forge

**An AI-powered monster generator for the [Nimble RPG](https://nimblerpg.com/) system, backed by a structured Airtable database.**

Generate mechanically balanced, thematically rich monsters using Claude's API — with stats that follow Nimble's official Monster Builder rules — and save them directly to an Airtable bestiary with one click.

Built as a full-stack portfolio project combining prompt engineering, REST API integration, relational data modeling, and a custom local web application.

---

## What It Does

1. **You define your party** — classes, levels, number of heroes
2. **You set the encounter parameters** — difficulty, theme (cosmic horror, sword-and-sorcery, etc.), environment, size, legendary toggle
3. **The AI generates a complete monster** — name, HP, armor, attacks, special abilities, lore, GM tips, and encounter balance notes — all mechanically valid against Nimble's stat tables
4. **One click saves it to Airtable** — populating a structured Monsters table with proper field types, ready to browse, filter, and use in session prep

The system prompt encodes the complete Nimble Monster Builder reference table (23 levels of HP/DPR/Save DC by armor type), the Legendary Monster stat table, die size theming rules, special ability balancing tradeoffs, and encounter math — so every generated creature is playable out of the box, not just flavor text.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Browser (localhost)              │
│  ┌─────────────────────────────────────────┐ │
│  │         Nimble Monster Forge UI          │ │
│  │  Party builder · Theme/env selectors    │ │
│  │  Stat block renderer · Export tools     │ │
│  └──────────────┬──────────────────────────┘ │
└─────────────────┼───────────────────────────┘
                  │ POST /api/claude
                  │ POST /api/airtable
                  ▼
┌─────────────────────────────────────────────┐
│         Python Proxy Server (local)          │
│  Handles CORS · Routes API calls            │
│  Zero dependencies · Single file            │
└────────┬────────────────────┬───────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│  Anthropic API   │  │  Airtable API    │
│  Claude Sonnet   │  │  REST v0         │
│                  │  │                  │
│  System prompt   │  │  Creates record  │
│  with full       │  │  in Monsters     │
│  Nimble monster  │  │  table with      │
│  builder rules   │  │  typed fields    │
└─────────────────┘  └─────────────────┘
```

**Why a proxy server?** The Anthropic API doesn't serve CORS headers, so browsers block direct calls from frontend JavaScript. The Python server relays requests from the browser to both APIs, keeping everything in a single zero-dependency file.

---

## Airtable Data Model

The Airtable base contains four relational tables:

**Characters** — Party members with stats (STR/DEX/INT/WIL), class, level, ancestry, equipment. Linked to Campaign Tags.

**Monsters** — AI-generated and official creatures. Fields: Name, Level, HP, Armor Type, Speed, Size, DPR, Save DC, Attack Description, Special Abilities, Monster Family, Environment Tags, Legendary fields (Bloodied, Last Stand, Last Stand HP), Source, Notes.

**Encounters** — Links Characters to Monsters. Rollup fields auto-calculate total hero levels and total monster levels. A formula field computes the difficulty ratio percentage.

**Campaign Tags** — Thematic tags (e.g., "Shadow of the Elderwild", "Farhope Faction Wars") that link to both Characters and Encounters for filtering.

The schema mirrors Nimble's design: fractional monster levels (0.25, 0.33, 0.5), three armor types (None/Medium/Heavy), and the encounter balance math (monster levels ÷ hero levels = difficulty).

---

## Prompt Engineering

The system prompt is the core of this project. Rather than asking the AI to "make up a monster," it provides the complete mechanical framework as structured reference data:

- **The full Monster Builder stat table** (23 rows) — so the AI looks up the correct HP, damage, and save DC for any level
- **The Legendary Monster stat table** (20 rows) — indexed by party level with separate columns for small/big attack damage and Last Stand HP
- **Balancing rules** — "for each special ability, lower HP or damage by 1 row" — the AI must state which tradeoff it made
- **Die size theming** — d4 for undead, d6 for goblins, d8 for humans, d10 for beasts, d12 for giants
- **Output constraints** — strict JSON schema, no double quotes in strings, single-line values — to ensure reliable parsing

The output is structured JSON that maps directly to Airtable field names, eliminating manual data entry.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Vanilla HTML/CSS/JS (embedded in server) |
| Backend | Python 3 standard library (http.server, urllib) |
| AI | Anthropic Claude API (Sonnet) |
| Database | Airtable (REST API v0) |
| Deployment | Single-file local server, zero dependencies |

---

## Setup

### Prerequisites
- Python 3.6+
- An [Anthropic API key](https://console.anthropic.com/settings/keys) (Sonnet costs ~$0.01 per monster)
- An [Airtable account](https://airtable.com) with a personal access token

### 1. Clone and run
```bash
git clone https://github.com/YOUR_USERNAME/nimble-monster-forge.git
cd nimble-monster-forge
python nimble_forge_server.py
```

### 2. Open http://localhost:8000

### 3. Click Settings and enter your API keys
- **Anthropic API Key** — from console.anthropic.com/settings/keys
- **Airtable Token** — from airtable.com/create/tokens (needs `data.records:write` scope)
- **Base ID** and **Table ID** — from your Airtable URL (`airtable.com/appXXX/tblXXX`)

Keys are stored in your browser's localStorage — never sent anywhere except the respective APIs.

### 4. Set up the Airtable base
Import the provided CSV seed files to bootstrap your tables:
- `monster_builder_reference.csv` — the official stat table
- `legendary_monster_builder_reference.csv` — legendary stat table
- `bestiary_seed_data.csv` — 18 monsters from the Nimble GMG

Or create the Monsters table manually with these fields: Name (text), Level (number), HP (number), Armor Type (single select), Speed (number), Size (single select), Damage Per Round (number), Save DC (number), Attack Description (long text), Special Abilities (long text), Monster Family (text), Environment Tags (text), Is Legendary (checkbox), Bloodied Ability (long text), Last Stand Ability (long text), Last Stand HP (number), Advantaged Saves (text), Source (single select), Notes (long text).

---

## What I Learned

- **Prompt engineering for structured output** — getting an LLM to produce reliably parseable JSON requires explicit constraints on string formatting (no double quotes, no newlines), a strict schema, and defensive parsing on the client side
- **Airtable's API field type semantics** — Single Select fields need `{name: "value"}`, Multiple Select needs `[{name: "value"}]`, and mismatches produce opaque errors
- **CORS as an architectural constraint** — browser security policies shaped the entire architecture (adding the proxy server), which is a real-world pattern used in production systems
- **Domain-specific AI applications** — embedding reference tables and mechanical rules in a system prompt transforms a general-purpose LLM into a specialized tool that produces usable output, not just plausible-sounding text

---

## File Structure

```
nimble-monster-forge/
├── nimble_forge_server.py          # Server + embedded frontend (run this)
├── monster_builder_reference.csv   # Nimble stat table for Airtable import
├── legendary_monster_builder_reference.csv
├── bestiary_seed_data.csv          # 18 pre-built monsters
└── README.md
```

---

## License

This project is a personal portfolio piece. The Nimble RPG system is © 2025 Nimble Co. Monster stat tables are referenced under the [Nimble 3rd Party Creator License](https://nimblerpg.com/creators).
