# Resolving real Tenable plugin IDs

Read this before building `current.json`. The tracker's `plugin_id` must be the **Tenable plugin ID that
Tenable itself attached to the finding** — never a GORR-generated action ID. Grouping into remediation
actions is a label (`action_id` / `action_name`), not a substitute for the plugin ID.

## 1. Why this needs work

`tenable_one_search_findings` returns only finding ID, name, asset ID, state and severity. The plugin ID
lives in the finding property `finding_detection_id`, which the search output does not print, and the
inventory export only echoes a few fields. So the ID has to be resolved and then confirmed.

## 2. Confirm an ID against the tenant (the evidence)

```
tenable_one_search_findings(filters='[{"property":"finding_detection_id","operator":"contains","value":["<plugin_id>"]}]')
```
- A hit on the expected asset(s) = confirmed. Mark the plugin `verified: true`.
- `"="` does not match; use `"contains"`. Multiple values in one `contains` filter are NOT OR'd — one ID per call.
- `contains` is a substring match: ignore unrelated hits (e.g. CVE-named findings whose detection ID happens to contain the digits).

## 3. Find the candidate ID (plugin database)

Tenable finding names are the exact plugin titles, so an exact title match is authoritative.
`plugins_search_plugins(query=...)` accepts **one distinctive token** per call — phrases and `OR` return nothing.

| Finding name contains | Query with | Example |
|---|---|---|
| `KBnnnnnnn:` rollup | the KB | `KB5003681` → 150354 |
| `MSxx-yyy: … (nnnnnnn)` bulletin | the KB number in parentheses (bulletin IDs are noisy) | `3143141` → 89755 (MS16-032) |
| Monthly rollup with no KB in the title ("… May 2017 Security Updates") | that month's rollup KB | `KB4019215` → 100057 |
| "Security Updates for Internet Explorer (Month YYYY)" | the IE cumulative KB for that month | `KB5005563` → 153374 |
| Adobe Flash / Reader / Acrobat (APSB…) | the **version string** in the title (APSB queries return thousands) | `17.0.0.188` → 84048; `2018.009.20044` → 104627 |
| MS KB for Flash in IE | the KB | `KB3065823` → 84645 |

Pick the result whose title matches the finding name exactly: watch Windows vs "(Mac OS X)/(macOS)",
Reader vs Acrobat, and "(uncredentialed check)" variants (97737 vs 97833 for MS17-010).

## 4. Same title, different sensor → always confirm

Nessus and NNM (passive) sometimes publish plugins with identical titles. Confirm with §2 whenever the
search returns more than one exact-title match. Seen in practice:
- DOUBLEPULSAR: tenant carried **NNM 700059**, not Nessus 99439.
- Flash APSB15-02: tenant carried **Nessus 80946**, not NNM 8658.
Record the sensor in `plugin_source` (Nessus / NNM / WAS / OT).

Minimum verification: every ambiguous title, every Phase 1 plugin, plus a spot check per plugin family.

## 5. Findings with no Tenable plugin

CVE-named findings (e.g. "CVE-2017-11882" on endpoints) and generic names from code/container sources
("Remote Code Execution (RCE)", "Out-of-bounds Write") usually come from third-party connectors. Test one:
look up the Tenable plugin that covers the CVE (`plugins_search_plugins(cve=...)`) and confirm it with §2. If it
does not match, the finding carries no Tenable plugin:
- `plugin_id` = the CVE (or the source's finding name), `plugin_source` = `Third-party`
- `plugin_name` = "<CVE> — third-party detection (no Tenable plugin)"
- Label it "3rd-party" in the dashboard. Never invent an ID, and never present the covering plugin as the finding's ID.
  A Nessus scan/agent on those hosts will give real plugin IDs on a later run.

## 6. Budget

Each ID costs one search (+ one confirmation when needed). Resolve what the **phased** plan needs first
(Phases 1–4); resolve backlog/next-cycle items when they enter a phase. If the turn's tool budget runs out,
report what is resolved, what remains, and continue on the next turn — do not fall back to made-up IDs.
Cache resolved IDs in a label → (id, title, sensor, verified) map and reuse it across runs.
