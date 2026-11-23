# GORR (Game Over Risk Reduction) — Tenable Quick Wins Executive Dashboard

A Claude Code skill that generates an interactive executive dashboard showing which vulnerabilities to close in order to reduce the Tenable One Exposure Score across **N cumulative phases (you choose 2–6; default 4 = 10% → 20% → 30% → 40%) delivered within a 30-day cycle**, plus a remediation ticket tracker (owner, ticket #, assignee, status) that is exported as CSV/JSON and re-imported on the next run to verify what was actually fixed.

## What it does

- Connects to the **Tenable One MCP** to pull live vulnerability data, Exposure Score, Crown Jewels, and attack path chokepoints
- Calculates a **Quick Win Score** for each finding: `(VPR × breadth × exploit_factor) / effort` with bonuses for Crown Jewels (+30%) and chokepoints (+20%)
- Targets the **official Exposure Score** from the Tenable One Exposure View API (an uploaded `gorr_exposure_view_*.json` or a fresh pull with the bundled collector), with the computed score as a cross-check
- Models how each module moves the Global score, **Identity Exposure IoEs included**, so the plan pulls the levers that actually carry the score
- Assembles **N cumulative, dated phases** (2–6, asked at the start of every run) inside a 30-day cycle; on the default 4 phases they are due D+7, D+14, D+21, D+30
- Records **when the skill ran and the next run date** (D+30), with countdown and `.ics` calendar reminder
- Keys every item on the **real Tenable plugin ID** (Nessus / NNM / WAS / OT), resolved and verified against the tenant; third-party detections keep their CVE and are labelled as such
- Groups plugins into **remediation actions** (one rollup, one uninstall) for phasing and one-ticket bulk assignment
- Flags **active-compromise indicators** (e.g. DOUBLEPULSAR) with an IR banner and pins them to Phase 1
- Takes the **owner of each asset from its Tenable tag** (configurable owner tag category, e.g. `Owner`, `Business Unit`), re-read every run — re-tag in Tenable and the items move to the new owner; reports owner-tag coverage and untagged / multi-owner assets
- Builds a **remediation tracker** (`gorr_tracker.csv` / `gorr_tracker.json`, one row per vulnerability × asset) for owner, assignee, ticket number and status — `scripts/tracker.py` merges it back on the next run
- On tracking runs, compares against the previous run: **fixed (verified) / still open / reopened / new / not re-scanned / overdue / "claimed resolved but still detected"**
- **Carry-over check:** flags every item from a past-due phase that is not fixed in Tenable or whose ticket is not closed, classifies why (blocked, no ticket, claimed-but-detected, unverified, exception, ticket-only), computes how many Exposure Score points each phase target loses and whether it will still be reached, and proposes a recovery phase, due date, mitigation action and escalation level (L1–L3) — all written into the CSV/JSON (`carryover_*`, `recovery_*` columns) and shown in a dedicated **Carry-over** tab
- Delivers a **fully interactive HTML dashboard** with:
  - Run-cycle banner (executed on, next run, phase due dates, comparison tiles)
  - Gauge/speedometer showing current score vs. 4 phase targets
  - Clickable phase cards with three tabs each: **By vulnerability** (one row per Tenable plugin in the phase, grouped by action → affected assets), **By asset** (each asset lists all its plugins in the phase, type-aware for devices and identities), **Tickets** (inline-editable tracker with CSV/JSON download and in-browser import) and **Carry-over** (impact on each phase target, breakdown by cause and owner, editable recovery plan)
  - Progression chart (Baseline → F1 … FN) with planned vs. actual score and industry benchmark
  - Peer benchmark card with percentile positioning before and after remediation
  - Executive summary block in plain business language (board-ready)
  - Method & data limits section that labels every proxy (score, VPR band, Crown Jewel) and unavailable input

## Audience

C-Level, Board, CISO, VP of IT, MSSP partners, Channel SEs demonstrating Tenable One value.

## Requirements

- **Tenable One MCP** connected (provides live vulnerability and Exposure Score data)
- Claude Desktop or Claude Code with skills support
- Optional: Tenable API keys on your own machine for the Exposure View collector (keys never go through the chat)

## Installation

Place the `gorr/` folder in your Claude Code skills directory:

```
~/.claude/skills/gorr/
```

## Usage

Invoke naturally in conversation:

```
"Show me our quick wins to reduce the exposure score"
"Build a remediation roadmap for C-Level"
"Which vulnerabilities should we close first this month?"
"Here is the filled tracker — what did we actually fix?"
"What did we miss from phase 1 and 2, and can we still hit the target?"
"Give me a phased plan to reduce our Tenable score"
"Where do we start to get the most impact with least effort?"
```

The skill will automatically:
1. Pull live data from Tenable One MCP
2. Compute Quick Win Scores
3. Assemble the N dated phases (your answer at the start of the run) and start a 30-day cycle
4. Write the tracker (CSV + JSON) and render the interactive dashboard

**Next run (≈30 days later):** upload the filled `gorr_tracker.json` (keeps full score history) or `gorr_tracker.csv` (Excel `;` or `,`, EN/PT status values accepted) and ask for the follow-up — the skill verifies each item in Tenable and shows what was fixed.

If the MCP is unavailable, a **DEMO** dashboard with realistic mock data is generated with a clear watermark.

## Customizations

| Request | Behavior |
|---------|----------|
| "3 phases" / "5 phases" | Plans that many phases (2–6) inside the 30-day cycle |
| "5 phases to 40%" | Sets a total instead of 10% per phase (8 / 16 / 24 / 32 / 40%) |
| "Focus on Cloud / Identity / OT" | Filters quick wins by domain |
| "Portuguese version" | Renders dashboard in Portuguese |
| "For the board" | Expands executive summary, condenses technical tables |
| "Include regulatory context" | Maps actions to LGPD, ISO 27001, NIST CSF, PCI-DSS |
| "Show only Crown Jewels" | Filters to findings affecting Crown Jewels |
| "Tracker in Excel" | Tracker delivered as .xlsx with status dropdown |
| "Group by owner" | Reorganizes tables by the Tenable-tag owner |
| "Owner is tag X" | Uses tag category X as the owner of each asset |

## How the Quick Win Score works

A Quick Win is a remediation action that maximizes:

```
QW Score = (VPR × breadth × exploit_factor) / effort
           + crown_jewel_bonus (+30%)
           + chokepoint_bonus (+20%)
```

This is **not CVSS** — it prioritizes real-world impact combined with execution feasibility. A single patch that closes 50 assets ranks far higher than 50 individual patches with the same severity.

## Design

Dark theme with Tenable brand palette:
- Background: `#44494B`
- Accent: `#E7FF00` (Yellow)
- Phase colors: `#71FFC6` → `#4EA5FF` → `#BB8FF2` → `#FF8837`; overdue/blocked `#FF4B4B`

## License

MIT
