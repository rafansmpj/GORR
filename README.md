# GORR (Game Over Risk Reduction) - Claude Desktop Skill

A Claude Desktop skill that works with the Tenable Hexa AI MCP to build a 30-day plan for cutting the Tenable One Exposure Score in cumulative phases of Quick Wins, plus a ticket tracker that proves what was actually fixed.

**Version 1.2.1** · tracker schema `gorr-tracker/1.2` · see [CHANGELOG](gorr/CHANGELOG.md)

## What it does

GORR builds an interactive executive dashboard that shows which vulnerabilities to close, in which order and by which date, to reduce the Tenable One Exposure Score across **N cumulative phases inside a 30-day cycle**. You choose N (2–6) at the start of every run. The default is 4 phases: 10% → 20% → 30% → 40%.

- **Official score.** It targets the official Exposure Score from the Tenable One Exposure View API: an uploaded `gorr_exposure_view_*.json` file, or a fresh pull with the bundled collector. The computed score is used as a cross-check.
- **Module levers.** It models how each module moves the Global score, Identity Exposure IoEs included, so the plan pulls the levers that actually carry the score.
- **Quick Win ranking.** Actions are ranked by projected score drop per unit of effort, with Crown Jewel (+30%) and attack path chokepoint (+20%) bonuses. Every item is keyed on the real Tenable plugin ID, verified against the tenant.
- **Owners from Tenable tags.** The owner of each asset is read from its Tenable tag on every run. Re-tag an asset in Tenable and its items move to the new owner.
- **Ticket tracker.** It writes `gorr_tracker.csv` / `gorr_tracker.json` (one row per plugin × asset) for owner, assignee, ticket number and status. Upload the tracker on the next run and GORR re-checks every item in Tenable: fixed (verified), still open, reopened, new, overdue, or "claimed resolved but still detected".
- **Carry-over.** Items from past-due phases that are not fixed or not closed are flagged, with their impact on each phase target and a recovery plan (phase, due date, mitigation, escalation L1–L3).
- **Read-only.** GORR never creates tickets or changes anything in Tenable.

The dashboard (English or Portuguese) includes a run-cycle banner, score gauge, clickable phase cards (By vulnerability, By asset, Tickets, Carry-over), progression chart (planned vs. actual), peer benchmark, board-ready executive summary, and a Method & data limits section that labels every proxy.

Audience: C-Level, Board, CISO, VP of IT, remediation teams, MSSP partners and Channel SEs.

SAMPLE:

<!-- Add a dashboard screenshot here (drag an image into the GitHub editor) -->

## Quick Start (5 minutes)

### 1. Prerequisites

- Claude Desktop (or Claude Code, or another Claude environment with skills support).
- A Tenable One MCP server (Tenable Hexa AI MCP) connected and authenticated. It provides findings, assets, tags, Crown Jewels and attack path data. Without it, the skill falls back to a "DEMO — illustrative data" dashboard so the workflow can still be shown end to end.
- The MCP connection needs read access to findings/vulnerabilities (VPR, severity, affected assets), assets and tags, Crown Jewels and attack paths.
- Optional, for the official Exposure Score: a Tenable API key pair with the Basic role or `EXPOSURE_MANAGEMENT.ANALYTICS.EXPOSURE_VIEW.READ`, used only by the collector script on your own machine. The keys never go through the chat.

### 2. Installation

Pick one:

- **Packaged skill:** download [`gorr.skill`](gorr.skill) and add it as a skill in Claude Desktop.
- **Folder:** copy the [`gorr/`](gorr) folder into your local skills directory:

```
~/.claude/skills/gorr/
```

The folder holds `SKILL.md`, `references/` (tracker schema, carry-over, MCP collection, plugin ID resolution), `scripts/tracker.py` (deterministic tracker merge) and `scripts/bump_version.py`. No build step: Python 3 is only needed for the tracker and collector scripts.

### 3. Configure

- Make sure the Tenable One MCP connector is active in the same Claude environment.
- **Owner tag category:** tag your assets with an owner category in Tenable (e.g. `Owner:Infra SP`, `Business Unit:Finance`). GORR auto-detects it by name, or tell it "owner is tag X".
- **Exposure View file (optional):** on the first run, choose "Generate a new file" and GORR gives you `gorr_exposure_view_pull.py`. Run it locally with your API keys from environment variables or a local keys file, then upload the `gorr_exposure_view_YYYYMMDD_HHMMSS.json` it writes.
- Optional context: industry (for the benchmark), language (EN/PT), and filters such as Crown Jewels only, one domain (Cloud / Identity / OT), or regulatory mapping (LGPD, ISO 27001, NIST CSF, PCI-DSS).

## Usage

Every run starts with two questions: which Exposure View file to use (uploaded, upload now, pull new, or continue without), and how many phases to plan.

```
"Run GORR with 4 phases"
"Show me our quick wins to reduce the exposure score"
"Which vulnerabilities should we close first this month?"
"Here is the filled tracker — what did we actually fix?"
"What did we miss from phase 1 and 2, and can we still hit the target?"
```

**The 30-day cycle**

1. **Baseline run:** GORR builds the phased plan and delivers the dashboard plus an empty tracker (CSV + JSON).
2. **During the cycle:** the team fills in ticket #, assignee and status in the tracker or in the dashboard's Tickets tab.
3. **Tracking runs:** upload `gorr_tracker.json` (keeps the full score history) or `.csv`. GORR verifies each item in Tenable and flags carry-over after each due date.
4. **Next cycle:** on the `next_run_date`, GORR closes the cycle and plans the next one with carried-over items.

## Repository layout

```
GORR/
├── README.md                 this file
├── LICENSE                   MIT
├── gorr.skill                packaged skill, ready to install
├── gorr/                     skill source
│   ├── SKILL.md
│   ├── README.md
│   ├── CHANGELOG.md
│   ├── VERSION
│   ├── listing.yaml
│   ├── references/
│   └── scripts/
├── skill-template.md         CyberAgents Exchange listing for GORR
├── playbook-template.md      Exchange template (playbooks)
└── mcp-server-template.md    Exchange template (MCP servers)
```

## Versioning

Run `python gorr/scripts/bump_version.py <major|minor|patch> "summary"` to bump `VERSION`, `SKILL.md`, `listing.yaml` and the CHANGELOG together, then rebuild `gorr.skill`.

## License

MIT — see [LICENSE](LICENSE).
