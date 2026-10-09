# Screenshots

In build order. The account ID is masked in every image.

| # | File | What it shows |
|---|---|---|
| 01 | [`01-lf-settings-snapshot-and-missing-default-database.png`](screenshots/01-lf-settings-snapshot-and-missing-default-database.png) | Lake Formation settings snapshot already saved; Athena's `default` database not found, then created; the cross-account version variable at `"4"` |
| 02 | [`02-quality-gates-fmt-validate-tflint-checkov.png`](screenshots/02-quality-gates-fmt-validate-tflint-checkov.png) | `terraform init`, `fmt` clean, `validate` success, `tflint` clean, checkov 139 passed / 36 failed |
| 03 | [`03-plan-lake-formation-admin.png`](screenshots/03-plan-lake-formation-admin.png) | The base plan's Lake Formation settings block: me as data lake administrator |
| 04 | [`04-apply-base-60-added.png`](screenshots/04-apply-base-60-added.png) | `Apply complete! Resources: 60 added`, and the outputs |
| 05 | [`05-saved-outputs-state-list.png`](screenshots/05-saved-outputs-state-list.png) | Outputs saved for the build, consumer mode `polling (shared throughput)`, 64 entries in the state |
| 06 | [`06-kinesis-stream-summary.png`](screenshots/06-kinesis-stream-summary.png) | The stream: ACTIVE, PROVISIONED, 2 shards, 24 h, KMS `alias/aws/kinesis`, `IncomingRecords` per shard |
| 07 | [`07-firehose-parquet-and-glue-tables.png`](screenshots/07-firehose-parquet-and-glue-tables.png) | Firehose: Kinesis source, `dt=` prefix, 64 MB / 60 s buffer, Parquet from `fleet_live`; the Glue tables |
| 08 | [`08-lake-formation-grants-and-analyst-workgroup.png`](screenshots/08-lake-formation-grants-and-analyst-workgroup.png) | Grants on `fleet_live` (analyst: 10 columns; Firehose: DESCRIBE + SELECT; my implicit rights), `default` with `IAM_ALLOWED_PRINCIPALS`, the analysts workgroup (1 GB, enforced) |
| 09 | [`09-lake-formation-settings-during-build.png`](screenshots/09-lake-formation-settings-during-build.png) | Lake Formation settings during the build: admin Michael-admin, empty defaults, version 4 |
| 10 | [`10-simulator-ready-code-hashes-match.png`](screenshots/10-simulator-ready-code-hashes-match.png) | The simulator booted; every tool file's SHA-256 on the server matches Terraform's output |
| 11 | [`11-backfill-7-days-raw-json.png`](screenshots/11-backfill-7-days-raw-json.png) | Backfill: 36,288,000 pings, 168 files, 7.19 GB in S3 |
| 12 | [`12-q1-q2-on-raw-json.png`](screenshots/12-q1-q2-on-raw-json.png) | Q1 and Q2 on the raw JSON: 7.19 GB scanned each |
| 13 | [`13-ctas-migration-and-history-partitions.png`](screenshots/13-ctas-migration-and-history-partitions.png) | The CTAS in `mvela-migration`; 210 Parquet files, 458.87 MB; 7 partitions of 5,184,000 pings |
| 14 | [`14-history-grant-plan-and-apply.png`](screenshots/14-history-grant-plan-and-apply.png) | `history_ready`: the analyst's grant on `fleet_history`, `1 added` |
| 15 | [`15-q1-parquet-with-and-without-dt.png`](screenshots/15-q1-parquet-with-and-without-dt.png) | Q1 on Parquet with and without the `dt` filter: 23.95 MB both |
| 16 | [`16-q2-parquet-and-identical-answers.png`](screenshots/16-q2-parquet-and-identical-answers.png) | Q2 on Parquet: 40.41 MB; the three comparisons identical |
| 17 | [`17-fleet-simulator-started.png`](screenshots/17-fleet-simulator-started.png) | `fleet-sim` started: 300 trucks, one ping every 5 s |
| 18 | [`18-kinesis-incoming-records.png`](screenshots/18-kinesis-incoming-records.png) | Kinesis: 3,600 records a minute, 0 throttled, PutRecords latency |
| 19 | [`19-kinesis-records-per-shard.png`](screenshots/19-kinesis-records-per-shard.png) | Records per shard over 5 minutes |
| 20 | [`20-firehose-read-and-converted.png`](screenshots/20-firehose-read-and-converted.png) | Firehose: read from the stream, converted, 0 failed |
| 21 | [`21-firehose-delivered-and-freshness.png`](screenshots/21-firehose-delivered-and-freshness.png) | Firehose: delivered to S3, DataFreshness 70–74 s |
| 22 | [`22-first-live-parquet-files-no-errors.png`](screenshots/22-first-live-parquet-files-no-errors.png) | The first live Parquet files; `errors/` empty |
| 23 | [`23-lake-freshness-depot-view-alarms.png`](screenshots/23-lake-freshness-depot-view-alarms.png) | Lake freshness over 10 polls; the depot view; both alarms OK |
| 24 | [`24-alerts-polling-and-latency.png`](screenshots/24-alerts-polling-and-latency.png) | Alerts in polling mode: 190 alerts, no driver fields; PingToAlertLatency p50 763 ms |
| 25 | [`25-lambda-polling-invocations-errors.png`](screenshots/25-lambda-polling-invocations-errors.png) | The function in polling mode: 120 invocations a minute, 0 errors |
| 26 | [`26-lambda-polling-iterator-age-duration.png`](screenshots/26-lambda-polling-iterator-age-duration.png) | The function in polling mode: IteratorAge and duration |
| 27 | [`27-enhanced-fan-out-plan-and-apply.png`](screenshots/27-enhanced-fan-out-plan-and-apply.png) | `alerts_efo`: `2 to add, 1 to change, 1 to destroy`; the old mapping destroyed first |
| 28 | [`28-enhanced-fan-out-consumer-and-mapping.png`](screenshots/28-enhanced-fan-out-consumer-and-mapping.png) | The consumer ACTIVE; the mapping Enabled at LATEST on the consumer |
| 29 | [`29-alerts-enhanced-fan-out-and-latency.png`](screenshots/29-alerts-enhanced-fan-out-and-latency.png) | Alerts with enhanced fan-out: PingToAlertLatency p50 79 ms |
| 30 | [`30-lambda-efo-invocations-errors.png`](screenshots/30-lambda-efo-invocations-errors.png) | The function with enhanced fan-out: invocations, errors |
| 31 | [`31-lambda-efo-iterator-age-duration.png`](screenshots/31-lambda-efo-iterator-age-duration.png) | The function with enhanced fan-out: IteratorAge 109–180 ms, duration |
| 32 | [`32-stream-replay-one-truck.png`](screenshots/32-stream-replay-one-truck.png) | Stream replay for MV-0042: 37,800 records read, 120 pings |
| 33 | [`33-replay-window-from-the-lake.png`](screenshots/33-replay-window-from-the-lake.png) | The same window from the lake: 120 pings, max 82.5 km/h |
| 34 | [`34-lf-check-engineer-and-analyst-1-2.png`](screenshots/34-lf-check-engineer-and-analyst-1-2.png) | Access checks 0–2: the engineer reads driver columns; the analyst's summary works; `driver_phone` COLUMN_NOT_FOUND |
| 35 | [`35-lf-check-analyst-3-5.png`](screenshots/35-lf-check-analyst-3-5.png) | Access checks 3–5: `SELECT *` 10 columns; `fleet_history` 7 days; raw table TABLE_NOT_FOUND |
| 36 | [`36-lf-check-analyst-6-7.png`](screenshots/36-lf-check-analyst-6-7.png) | Access checks 6–7: engineering workgroup refused by IAM; S3 AccessDenied |
| 37 | [`37-lf-check-8-of-8.png`](screenshots/37-lf-check-8-of-8.png) | `RESULT lf-check: 8 of 8 as expected` |
| 38 | [`38-analyst-depot-view.png`](screenshots/38-analyst-depot-view.png) | The control-room view as the analyst, in `mvela-analysts` |
| 39 | [`39-lake-formation-console-admin-permissions.png`](screenshots/39-lake-formation-console-admin-permissions.png) | Lake Formation console: Michael-admin's implicit rights on what Terraform created |
| 40 | [`40-quick-sight-field-list-10-fields.png`](screenshots/40-quick-sight-field-list-10-fields.png) | Quick Sight's field list: 10 fields, no driver columns; lat/lon as geospatial |
| 41 | [`41-quick-sight-average-speed-by-depot.png`](screenshots/41-quick-sight-average-speed-by-depot.png) | Quick Sight: average speed per depot |
| 42 | [`42-quick-sight-grant-applied.png`](screenshots/42-quick-sight-grant-applied.png) | The Quick Sight user's grant: `1 added` |
| 43 | [`43-quick-sight-grant-removal-plan.png`](screenshots/43-quick-sight-grant-removal-plan.png) | Removing the Quick Sight grant: the plan |
| 44 | [`44-quick-sight-grant-removed.png`](screenshots/44-quick-sight-grant-removed.png) | Removing the Quick Sight grant: `1 destroyed` |
| 45 | [`45-quick-sight-unsubscribed.png`](screenshots/45-quick-sight-unsubscribed.png) | Quick Sight unsubscribed: termination protection off (200), subscription deleted (202) |
| 46 | [`46-simulator-stopped-firehose-hourly.png`](screenshots/46-simulator-stopped-firehose-hourly.png) | Fleet stopped: 414,660 sent, 0 lost; Firehose hourly read and delivered |
| 47 | [`47-live-files-final.png`](screenshots/47-live-files-final.png) | Firehose's final output: 230 files, 10.78 MB |
| 48 | [`48-results-summary-athena.png`](screenshots/48-results-summary-athena.png) | Results summary: Athena |
| 49 | [`49-results-summary-s3-stream.png`](screenshots/49-results-summary-s3-stream.png) | Results summary: comparisons, S3, backfill, producer |
| 50 | [`50-results-summary-alerts-replay.png`](screenshots/50-results-summary-alerts-replay.png) | Results summary: alerts, freshness, replay |
| 51 | [`51-results-summary-lake-formation-terraform.png`](screenshots/51-results-summary-lake-formation-terraform.png) | Results summary: Lake Formation checks and Terraform |
| 52 | [`52-destroy-plan-workgroups.png`](screenshots/52-destroy-plan-workgroups.png) | The destroy plan (workgroups being destroyed) |
| 53 | [`53-destroy-complete-62.png`](screenshots/53-destroy-complete-62.png) | `Destroy complete! Resources: 62 destroyed.` |
| 54 | [`54-lake-formation-settings-restored-identical.png`](screenshots/54-lake-formation-settings-restored-identical.png) | Lake Formation settings: still the project's after the destroy; restored; identical to the snapshot |
| 55 | [`55-clean-check.png`](screenshots/55-clean-check.png) | Clean check: state 0; only other projects' `mvelaphanda-*` resources match `mvela` |
