# Debugging journey

What didn't go as expected, what it turned out to be, and what changed. In the order it happened.

## 1. The account's Lake Formation cross-account version was 4, not 1

**Symptom.** The snapshot I took before the first apply showed `CROSS_ACCOUNT_VERSION` `"4"` and `SET_CONTEXT` `"TRUE"` in the settings' parameters ([`results/raw/lf-settings-before.json`](results/raw/lf-settings-before.json)). I had written the settings resource for an account on version 1.

**Cause.** The account was already on version 4. `aws_lakeformation_data_lake_settings` replaces the whole settings object, so whatever I didn't declare, Terraform would send as its own default. And, going by the provider's implementation, its delete resets the version to `"1"`.

**Fix.** A variable, `lf_cross_account_version`, defaulting to the account's `"4"`, and both parameters declared exactly as the API returns them. The plan showed the settings block with me as admin ([`03`](screenshots/03-plan-lake-formation-admin.png)), the settings during the build kept version 4 ([`09`](screenshots/09-lake-formation-settings-during-build.png)), and the teardown takes the resource out of state rather than letting its delete run ([ADR 0006](adr/0006-snapshot-and-restore-the-account-wide-lake-formation-settings.md)).

**Lesson.** Read an account-wide setting before writing code that replaces it, and never let a Terraform delete be the way it gets "restored".

## 2. Athena's `default` database didn't exist

**Symptom.** `aws glue get-database --name default` failed with `EntityNotFoundException` ([`01`](screenshots/01-lf-settings-snapshot-and-missing-default-database.png)).

**Cause.** The Athena console creates `default` the first time it's used; this account had only ever used Athena from the CLI. Athena describes `default` for every query, so the analyst role has to be able to see it. Created after Terraform cleared the account's default permissions, it would have been Lake Formation-only, and the analyst would have needed a grant on it.

**Fix.** Created it before the first apply (`aws glue create-database`, name `default`), while new databases still got `IAM_ALLOWED_PRINCIPALS`. After the apply it listed `IAM_ALLOWED_PRINCIPALS` ([`08`](screenshots/08-lake-formation-grants-and-analyst-workgroup.png)), and the analyst's queries worked.

## 3. Listing Lake Formation grants by principal needs a resource

**Symptom.** My first `aws lakeformation list-permissions --principal ...` to show the analyst's grants was refused.

**Cause.** Lake Formation filters grants by resource; a principal on its own isn't enough.

**Fix.** List by resource instead (`--resource '{"Table":{"DatabaseName":"mvela_fleet","Name":"fleet_live"}}'`), which shows every grant on the table: the analyst's 10 columns, Firehose's `DESCRIBE` and `SELECT`, and my implicit rights as the creator ([`08`](screenshots/08-lake-formation-grants-and-analyst-workgroup.png)).

## 4. A broken pipe reading a sample of the export

**Symptom.** Reading the first lines of an hourly file through a pipe into `head` ended in a broken-pipe error.

**Cause.** `head` closed the pipe after a few lines while the copy was still writing a 44 MB object into it.

**Fix.** Ask S3 for the bytes I need instead: `s3api get-object --range bytes=0-420`, two pings, no pipe.

## 5. The CTAS was rejected by an enforced workgroup

**Symptom.** The migration CTAS failed in `mvela-engineering` because it sets `external_location`.

**Cause.** A workgroup with `enforce_workgroup_configuration = true` decides where results go and won't let a query choose; a CTAS with `external_location` chooses where its table's files go. Both of my workgroups enforce their settings on purpose.

**Fix.** A third workgroup, `mvela-migration`, that doesn't enforce, keeps its own results folder and the 20 GB limit, and is only for one-off migrations (`Plan: 1 to add`). The CTAS ran there: 7.19 GB scanned once, 210 Parquet files ([`13`](screenshots/13-ctas-migration-and-history-partitions.png)). Loosening the engineering or analysts workgroup would have removed a guardrail for every other query ([ADR 0004](adr/0004-separate-athena-workgroups-with-scan-limits.md)).

## 6. A stale copy of my own code

**Symptom.** After adding the migration workgroup, the apply reported no changes and Athena said the workgroup didn't exist.

**Cause.** My working folder had been unpacked from an older copy of my own files, so its `athena.tf` didn't have the new block.

**Fix.** Added the block to the working copy; the plan then showed `1 to add` ([`results/raw/tf-plan-migration.txt`](results/raw/tf-plan-migration.txt)), the workgroup was created, and the CTAS ran in it. The history grant followed the CTAS (`1 added`, [`14`](screenshots/14-history-grant-plan-and-apply.png)). On the way I also stopped expecting output from my `grep -q ... || echo ... >>` guards: `grep -q` prints nothing whether it matches or not, so I check the phases file itself.

**Lesson.** When a plan says "no changes" after an edit, check the file Terraform is reading before anything else.

## 7. Quick Sight treated latitude and longitude as plain numbers

**Symptom.** The first chart of `lat` was a bar chart counting records per latitude value ("Count of Records by Lat", top 2,500 values).

**Cause.** Athena returns `double`; Quick Sight doesn't infer that a column named `lat` is a coordinate.

**Fix.** In the dataset, set `lat` to Latitude and `lon` to Longitude; they then show with the geospatial icon in the field list ([`40`](screenshots/40-quick-sight-field-list-10-fields.png)).

## 8. The clean check matched another project

**Symptom.** After the destroy, the clean check printed four names: a Lambda function `mvelaphanda-resource-hygiene`, a bucket `mvelaphanda-cost-reports-...`, a role `mvelaphanda-resource-hygiene-role` and its log group ([`55`](screenshots/55-clean-check.png)).

**Cause.** My filters were `starts_with(..., 'mvela')`, which also matches `mvelaphanda-*`: resources from `aws-resource-hygiene-automation` and `aws-cost-billing-dashboard`, which are meant to be there. Nothing of this project was left: the state list was 0, every `mvela-` resource was gone, and the state file was an empty 610-byte state.

**Fix.** The filters in [`teardown.md`](teardown.md) use `mvela-` (with the hyphen).

**Lesson.** A naming prefix is only a filter if no other prefix starts with it. Tags (`Project = aws-streaming-analytics-lake`, on every resource here) are the more reliable filter, and the planned teardown tool will use them.
