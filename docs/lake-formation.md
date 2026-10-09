# Lake Formation: the analyst sees trucks, not drivers

## The setup

Two columns of every ping are personal information: `driver_id` and `driver_phone`. Engineering needs them (to fix the export, to answer a legal request); operations analysts and the control-room dashboard don't. IAM can allow or deny a table's files, but it can't hide two columns of a file. Lake Formation can: it holds grants per database, table and column, and engines that read through it (Athena here, Quick Sight through Athena) get only what the caller was granted.

What Terraform declares ([`infra/lakeformation.tf`](../infra/lakeformation.tf)):

- **The account's data lake settings:** me (the identity running Terraform) as data lake administrator; the default permissions for new databases and tables left out, which **clears** them, so new databases are Lake Formation-controlled instead of "IAM only"; the cross-account version pinned to the value the account already had (`"4"`).
- **`curated/` registered** with its own role (`mvela-lf-registration-role`), which Lake Formation uses to hand engines temporary credentials for that location. `raw/` stays unregistered: only engineering reads it, through IAM.
- **Grants:** the analyst role gets `SELECT` on an **allow-list of 10 columns** of `fleet_live` (and of `fleet_history` once it exists, `history_ready = true`); Firehose's role gets `DESCRIBE` + `SELECT` on `fleet_live`, because reading the table's schema for Parquet conversion is a catalog read that Lake Formation now governs; the optional Quick Sight user gets the analyst's 10 columns.
- **The analyst role** (`mvela-ops-analyst`, assumable only by me in this lab): Athena in `mvela-analysts` only, catalog reads, `lakeformation:GetDataAccess`, and its own folder of query results. **No S3 permission on the lake at all.**

The allow-list is `truck_id, depot, event_ms, lat, lon, speed_kmh, heading, engine_on, fuel_pct, dt`. An allow-list rather than "everything except the driver columns" means a column added to the export later stays hidden until someone decides it isn't personal ([ADR 0003](adr/0003-lake-formation-column-allow-list.md)).

## What AWS showed after the apply

- **Settings during the build:** admins `user/Michael-admin`, both default-permission lists empty, `CROSS_ACCOUNT_VERSION` `"4"`, `SET_CONTEXT` `"TRUE"` ([`09`](screenshots/09-lake-formation-settings-during-build.png)).
- **Grants on `fleet_live`:** `mvela-ops-analyst` with the 10 column names and `SELECT`; `mvela-firehose-role` with `DESCRIBE` and `SELECT`; and lines for Michael-admin that I never granted ([`08`](screenshots/08-lake-formation-grants-and-analyst-workgroup.png)). The console shows the same for every database and table I created, `default` included ([`39`](screenshots/39-lake-formation-console-admin-permissions.png)): Lake Formation gives the creator of a database or table full rights on it, and an administrator can see everything anyway.
- **The `default` database** listed `IAM_ALLOWED_PRINCIPALS`: it was created before the settings changed, so IAM still governs it, and the analyst role can describe it through IAM (Athena describes `default` for every query).
- **The analysts workgroup:** 1,073,741,824 bytes (1 GB) per query, enforced, results in its own `analysts/` folder, Athena engine version 3.

## The eight checks

[`scripts/lf_check.py`](../scripts/lf_check.py) runs one check as me and seven as the analyst (it assumes the role and never prints the keys). A check only passes for the right reason: a refusal from the 1 GB scan limit, for example, would count as a failure.

| # | Who / what | Expected | Result |
|---|---|---|---|
| 0 | Engineer reads `truck_id, driver_id, driver_phone` | works | **SUCCEEDED**, 3 rows (fake numbers `+27 000 000 nnn`) |
| 1 | Analyst: pings and average speed per depot | works | **SUCCEEDED**, 4 rows, 879.68 KB scanned |
| 2 | Analyst asks for `truck_id, driver_phone` | refused | **FAILED: `COLUMN_NOT_FOUND`**: the column "cannot be resolved or requester is not authorized" |
| 3 | Analyst `SELECT *` | 10 columns, no `driver_*` | **SUCCEEDED, 10 columns**: `truck_id, depot, event_ms, lat, lon, speed_kmh, heading, engine_on, fuel_pct, dt` |
| 4 | Analyst reads `fleet_history` per day | works | **SUCCEEDED, 7 days**, 0 B scanned |
| 5 | Analyst reads `raw_pings_json` | refused | **FAILED: `TABLE_NOT_FOUND`**: to the analyst, the table doesn't exist |
| 6 | Analyst runs a query in `mvela-engineering` | refused by IAM | **`AccessDeniedException`** on `athena:StartQueryExecution` |
| 7 | Analyst lists the lake bucket with S3 | AccessDenied | **`AccessDenied`** on `ListObjectsV2`: no identity-based policy allows it |

**`RESULT lf-check: 8 of 8 as expected`** ([`34`](screenshots/34-lf-check-engineer-and-analyst-1-2.png)–[`37`](screenshots/37-lf-check-8-of-8.png), [`results/lake-formation-checks.csv`](results/lake-formation-checks.csv)).

Check 4 scanned 0 bytes: counting rows per day needs no column data, and the row counts are in each Parquet file's footer, which is most likely where Athena answered it from.

The analyst's own control-room view in `mvela-analysts` worked the same as mine (4 depots, 292.19 KB scanned, [`38`](screenshots/38-analyst-depot-view.png)). Its numbers differ from my earlier run because "the last 15 minutes" was a different 15 minutes.

## The dashboard: Amazon Quick Sight

On the free trial, with Athena as the source in the `mvela-analysts` workgroup and the Quick Sight user granted exactly the analyst's 10 columns by Terraform (`quicksight_principal_arn`, `1 added`, [`42`](screenshots/42-quick-sight-grant-applied.png)):

- The dataset's **field list showed 10 fields**, no `driver_id`, no `driver_phone` ([`40`](screenshots/40-quick-sight-field-list-10-fields.png)). The BI tool never sees the personal columns, with no filtering configured in the BI tool.
- I set `lat` and `lon` as latitude and longitude and built the control room's bar chart of average speed per depot ([`41`](screenshots/41-quick-sight-average-speed-by-depot.png)).
- Then the grant came off first, while the Quick Sight user still existed so Lake Formation could revoke it cleanly (`1 destroyed`, [`43`](screenshots/43-quick-sight-grant-removal-plan.png), [`44`](screenshots/44-quick-sight-grant-removed.png)), and the subscription was cancelled: termination protection off (`200`), `delete-account-subscription` (`202`) ([`45`](screenshots/45-quick-sight-unsubscribed.png)).

Signing up creates service roles for Quick Sight in IAM, and cancelling doesn't remove them; they cost nothing.

## The account-wide trap, and putting it back

Lake Formation's settings belong to the whole account, not to this project. While the project existed, every new Glue database in the account would have been Lake Formation-only, and an unrelated project's Athena tables would have been invisible to anyone without a grant.

Destroying `aws_lakeformation_data_lake_settings` would not have put the account back: going by the provider's implementation, its delete clears the administrators and the default permissions and sets the cross-account version to `"1"`. So ([ADR 0006](adr/0006-snapshot-and-restore-the-account-wide-lake-formation-settings.md)):

1. **Before the first apply**, `scripts/lf_settings.py snapshot` saved the settings: no administrators, `IAM_ALLOWED_PRINCIPALS` with `ALL` as the default for new databases and tables, `CROSS_ACCOUNT_VERSION` `"4"`, `SET_CONTEXT` `"TRUE"` ([`results/raw/lf-settings-before.json`](results/raw/lf-settings-before.json)).
2. **Before the destroy**, `terraform state rm aws_lakeformation_data_lake_settings.this`: Terraform forgets the resource, nothing changes in AWS, and I stay administrator while the destroy revokes the grants.
3. **After the destroy**, `show` still printed the project's settings (admin Michael-admin, empty defaults); `restore` wrote the snapshot back (no admins, `IAM_ALLOWED_PRINCIPALS=ALL` for both); `diff`: **`lf-settings: identical to the snapshot taken before the build`** ([`54`](screenshots/54-lake-formation-settings-restored-identical.png)).
