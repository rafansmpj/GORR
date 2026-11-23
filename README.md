# GORR (Game Over Risk Reduction) - Claude Desktop Skill

A Claude Desktop skill that works with the Tenable Hexa AI MCP to build a 30-day plan for cutting the Tenable One Exposure Score in cumulative phases of Quick Wins, plus a ticket tracker that proves what was actually fixed.

**Version 1.2.1** · tracker schema `gorr-tracker/1.2` · see [CHANGELOG](CHANGELOG.md)

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

## Quick Start (5 minutes)

### 1. Prerequisites

- Claude Desktop (or Claude Code, or another Claude environment with skills support).
- A Tenable One MCP server (Tenable Hexa AI MCP) connected and authenticated. It provides findings, assets, tags, Crown Jewels and attack path data. Without it, the skill falls back to a "DEMO — illustrative data" dashboard so the workflow can still be shown end to end.
- The MCP connection needs read access to findings/vulnerabilities (VPR, severity, affected assets), assets and tags, Crown Jewels and attack paths.
- Optional, for the official Exposure Score: a Tenable API key pair with the Basic role or `EXPOSURE_MANAGEMENT.ANALYTICS.EXPOSURE_VIEW.READ`, used only by the collector script on your own machine. The keys never go through the chat.

### 2. Installation

Pick one:

- **Claude Desktop:** download [`gorr.skill`](gorr.skill), then upload it in Claude Desktop's Skills settings.
- **Claude Code:** clone this repository into your skills directory. The skill is available in every project:

```
git clone https://github.com/rafansmpj/GORR.git ~/.claude/skills/gorr
```

  For a single project, clone it into `.claude/skills/gorr` inside that project instead. Invoke it with `/gorr` or by asking for GORR / quick wins.

The repository root is the skill: `SKILL.md`, `references/` (tracker schema, carry-over, MCP collection, plugin ID resolution), `scripts/tracker.py` (deterministic tracker merge) and `scripts/bump_version.py`. No build step: Python 3 is only needed for the tracker and collector scripts.

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

## Outputs

- `gorr_quick_wins_<YYYYMMDD>.html` — standalone interactive dashboard (English or Portuguese).
- `gorr_tracker.csv` / `gorr_tracker.json` — remediation tracker, one row per plugin × asset, re-imported on the next run.
- `gorr_exposure_view_pull.py` (only when you ask for a fresh pull) — local collector that writes `gorr_exposure_view_YYYYMMDD_HHMMSS.json`.
- An `.ics` reminder for the next run date.

## Data flows

GORR reads Tenable data through the Tenable One MCP connected to your Claude environment. The optional collector script calls only the Tenable One Exposure View API (`cloud.tenable.com`) from your own machine, with keys from your environment or a local keys file. Nothing is written back to Tenable, and no other outbound calls are made.

## Known limitations

- **Computed score without the Exposure View file.** If no Exposure View JSON is provided, the score is GORR's reconstruction of Tenable's model, labelled as a proxy in the dashboard. Projected drops per phase are estimates, not Tenable's own numbers.
- **MCP query limits.** Large tenants may not return every finding; the dashboard's Method & data limits section states the coverage actually retrieved (e.g. "400 of 552 VPR ≥ 9 findings").
- **Optional inputs.** The peer benchmark needs the Exposure View file; Crown Jewel and chokepoint bonuses need those features populated in Tenable One. When missing, GORR shows "n/a" or uses a labelled proxy (e.g. ACR ≥ 9 for Crown Jewels).
- **Verification depends on re-scans.** A fix is only confirmed once Tenable re-scans the asset; until then the item shows as "not re-scanned".
- **Owner tags.** Assets without an owner tag fall back to the tracker's `owner` column and are listed as untagged.
- **No ticketing integration.** GORR never creates or updates tickets; ticket data lives only in the tracker files.
- **Demo mode.** Without a working Tenable One MCP, the dashboard uses illustrative data with a "DEMO" watermark.

## Repository layout

```
GORR/
├── README.md                 this file
├── LICENSE                   MIT
├── SKILL.md                  skill instructions
├── CHANGELOG.md
├── VERSION
├── listing.yaml
├── references/               tracker schema, carry-over, MCP collection, plugin ID resolution
├── scripts/                  tracker.py, bump_version.py
├── gorr.skill                packaged skill for Claude Desktop
└── skill-template.md         CyberAgents Exchange listing for GORR
```

## Versioning

Run `python scripts/bump_version.py <major|minor|patch> "summary"` to bump `VERSION`, `SKILL.md`, `listing.yaml` and the CHANGELOG together, then rebuild `gorr.skill`.

## License

MIT — see [LICENSE](LICENSE).
