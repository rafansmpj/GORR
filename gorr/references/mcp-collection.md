# Tenable MCP collection — what works and the known gaps

Order of calls that produced a complete baseline, plus the workarounds for fields the MCP does not expose.

## Findings
- `tenable_one_search_findings(vpr_min="9.0", sort="finding_vpr_score:desc", filters='[{"property":"state","operator":"=","value":["ACTIVE"]}]', limit=200)`
  and page with `offset`. Also get totals for `vpr_min="8.0"` (used in the risk denominator).
- Combining `finding_vpr_score` inside `filters` returns HTTP 400; use the `vpr_min` convenience parameter.
- `tenable_one_export_inventory` filter values must be **string arrays** (`"value":["7.0"]`), otherwise 400.
  The chunk download echoes only ~5 records and a few fields — do not rely on it for bulk data.
- The search output gives only the VPR **band** you filtered on, not the exact score. Use the band floor
  (e.g. 9.0) and display "≥ 9.0". Do not invent exact VPRs.
- `workbenches_list_vulnerabilities` / `workbenches_get_asset_vulnerabilities` may return nothing even when
  Tenable One has findings; don't block on them.

## Assets
- `tenable_one_search_assets(filters='[{"property":"asset_id","operator":"=","value":[...ids]}]')` resolves up to
  ~50 IDs in one call → name, class (DEVICE, APPLICATION, CODE_REPOSITORY, CONTAINER…), AES, ACR.
- `workbenches_get_asset_info(asset_id)` → IPv4, OS, system type, last seen for VM/OT-scanned devices.
  Connector-sourced assets return an error → render "—".
- The first `search_assets` call can fail transiently; retry once.

## Tags → owner
- `tagging_list_tag_categories_and_values()` → every tag category and its values. Use it to pick / confirm the
  owner tag category (SKILL.md, "Owner from Tenable tags"). Demo and lab tenants often have **no** owner-like
  category — then ask the user rather than guessing from technical categories (OS, Software, ASM).
- Per-asset tags: take them from the asset records already fetched (`tenable_one_search_assets` / Tenable One
  inventory, or `workbenches_get_asset_info` for VM devices). Check `tenable_one_list_inventory_properties` for the
  tag property name on the tenant if tags do not appear in the default fields, and request it explicitly.
- Normalize to `Category:Value` strings in `current.json` → `asset_tags`. An asset whose tags could not be
  retrieved is left out of `asset_tags` (the script keeps its previous owner) — do not send an empty list for it,
  because an empty list means "confirmed: no owner tag".
- Never create or apply tags (`tagging_create_tag`, `tagging_add_tags_assets`) — the skill is read-only. Recommend
  tag rules to the user instead.

## Not exposed by the MCP (use the fallbacks, and say so in the dashboard)
| Missing | Fallback | Where to disclose |
|---|---|---|
| Tenable One Exposure Score (CES) | Proxy = mean AES of the 25 highest-AES devices; label "proxy" everywhere | Header, gauge, method section |
| Lumin industry benchmark / percentile | Show "n/a"; tell the user to read it from Exposure View | "Where you stand", exec summary |
| Crown Jewel tags (if none exist) | ACR ≥ 9 as critical-asset proxy, labelled "Critical (ACR ≥ 9)" | Tables, method section |
| Attack-path chokepoints | No chokepoint bonus; column shows "—" | Method section |
| Findings on some high-AES OT assets | Flag the gap by name (e.g. top-AES devices with no findings returned) | Method section |
