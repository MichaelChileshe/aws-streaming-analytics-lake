# 0003 · Lake Formation column grants as an allow-list; the analyst role gets no S3 access

**Status:** accepted · 2026-10-09

## Context
Each ping carries `driver_id` and `driver_phone`: personal information under POPIA. Engineering needs them; operations analysts and the dashboard don't. IAM can grant or deny objects in S3, not columns inside a file. Removing the columns from the data would break the engineering uses.

## Decision
- **Lake Formation governs the curated tables:** `curated/` is registered with a dedicated role; new databases get no `IAMAllowedPrincipals` grant, so Lake Formation decides who reads what.
- **Grants are an allow-list of columns** (`truck_id, depot, event_ms, lat, lon, speed_kmh, heading, engine_on, fuel_pct, dt`), defined once in `infra/main.tf` and reused for `fleet_live`, `fleet_history` and the dashboard user.
- **The analyst role has no S3 permission on the lake.** It gets Athena in its own workgroup, catalog reads and `lakeformation:GetDataAccess`; every byte it reads comes through Lake Formation's credential vending.
- **`raw/` stays unregistered and ungranted** to analysts: the raw table doesn't exist for them.

## Alternatives considered
- **An exclusion list ("all columns except driver_*"):** a column added later would be visible by default.
- **A view without the personal columns:** a view is only as strong as the permissions on the table under it, and with IAM alone the analyst would still need S3 access to the files.
- **A separate, stripped copy of the data:** two copies to keep in sync and pay for.
- **Data cells filters (row and column):** the right tool when rows must be filtered too (for example by depot); not needed for this requirement.

## Consequences
- Measured: 8 of 8 checks, including `COLUMN_NOT_FOUND` for `driver_phone`, 10 columns for `SELECT *`, `TABLE_NOT_FOUND` for the raw table, `AccessDenied` from S3. Quick Sight listed the same 10 fields.
- Every engine that reads the lake must integrate with Lake Formation; a tool reading S3 directly would need its own path.
- The setting that makes new databases Lake Formation-only is account-wide ([0006](0006-snapshot-and-restore-the-account-wide-lake-formation-settings.md)).
