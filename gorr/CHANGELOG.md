# GORR — Changelog & Release Tracker

All notable changes to the GORR skill. Format: [Keep a Changelog](https://keepachangelog.com),
versioning: [SemVer](https://semver.org).

- **MAJOR** — breaks existing trackers (item keys, required columns) or the dashboard contract
- **MINOR** — new views, tabs, customizations or collection logic; old trackers still load
- **PATCH** — wording, layout/CSS fixes, bug fixes, description tuning

Two versions are tracked independently:
- **Skill version** — `VERSION`, `SKILL.md` frontmatter `metadata.version`, `listing.yaml` `version`
- **Tracker schema** — `SCHEMA_VERSION` in `scripts/tracker.py` (only bumps when CSV/JSON fields change)

Use `python scripts/bump_version.py <major|minor|patch> "summary"` to bump all three files and open a new entry.

## Release history

| Version | Date | Tracker schema | Status | Summary |
|---------|------|----------------|--------|---------|
| 1.2.1 | 2026-11-23 | gorr-tracker/1.2 | Released | Description and Exchange listing aligned with current scope |
| 1.2.0 | 2026-09-28 | gorr-tracker/1.2 | Released | Owner of each asset from its Tenable tag (owner tag category) |
| 1.1.0 | 2026-09-25 | gorr-tracker/1.1 | Released (baseline) | Carry-over + recovery plan, real plugin IDs, GORE → GORR rename |
| 1.0.0 | 2026-06-22 | gorr-tracker/1.0 | Released | Initial release |

---

## [Unreleased]

### Added
### Changed
### Fixed

---

## [1.2.1] — 2026-11-23

### Changed
- SKILL.md description rewritten for the current scope: official Exposure Score from the Exposure View JSON
  (uploaded or pulled), module → Global model incl. Identity Exposure IoEs, 2–6 phases, EN/PT, read-only;
  stays under the 1,024-character limit
- `listing.yaml` description aligned with the same scope (N phases instead of fixed four, Exposure View,
  Identity Exposure, read-only); `identity-exposure` and `exposure-view` tags added


## [1.2.0] — 2026-09-28

### Added
- Owner of each asset taken from its Tenable tag in a configurable owner tag category (`owner_tag_category`,
  auto-detected by name when not set) and re-read every run — `references/tracker-schema.md` §10
- Tracker schema 1.2: `owner_source`, `owner_tag` columns; `COMPARISON.owner_coverage` and `COMPARISON.owners`
- Owner coverage strip + Owners mini-table in Section A2; Owner (tag) column in all tabs; per-owner bulk assign;
  owner coverage in Section G and the executive summary
- MCP collection notes for tag categories and per-asset tags
### Changed
- `owner` is no longer free text on tagged assets: the Tenable tag wins, typed owners move to `notes`;
  the column is read-only in the Tickets tab when it comes from a tag
- `suggested_owner_team` is a hint for untagged assets only; carry-over `by_owner` uses "No owner tag"


## [1.1.0] — 2026-09-25 — baseline for version tracking

> Reconstructed from the installed skill; this is the first version under formal tracking.
> Details of intermediate edits before today were not recorded.

### Added
- Carry-over check for past-due phases: classification, impact on each phase target, recovery plan,
  escalation L1–L3, Carry-over tab (Tab 4) — `references/carryover.md`
- Tracker schema 1.1 with `carryover_*` / `recovery_*` fields (1.0 files still load)
- Real Tenable plugin ID resolution and verification — `references/plugin-id-resolution.md`
- Remediation actions grouping plugins (`action_id`, `action_name`), bulk-assign per action
- Type-aware By-asset view for identity objects (IDENTITY / ACCOUNT / GROUP / RESOURCE)
- Active-compromise override (pinned to Phase 1 + red banner)
- Section G — Method & data limits

### Changed
- Renamed GORE → GORR; legacy `gore_tracker.*` files still accepted
- By vulnerability tab: one row per Tenable plugin in the phase; By asset tab lists every plugin per asset

## [1.0.0] — 2026-06-22

### Added
- Initial release: 4 cumulative phases (10/20/30/40%) in a 30-day cycle, Quick Win Score,
  CSV/JSON ticket tracker, tracking runs, executive dashboard
