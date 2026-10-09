# 0002 · Parquet partitioned by UTC day, with partition projection

**Status:** accepted · 2026-10-09

## Context
Athena charges for the bytes it reads. The export was uncompressed JSON in one flat folder, so every query read all of it: 7.19 GB for a question that needed 180 rows. New data arrives every minute, so new partitions appear constantly.

## Decision
- **Parquet with Snappy compression** for everything in `curated/`: Firehose converts the live stream using the Glue table's schema; one CTAS migrated the history.
- **One folder per UTC day** (`dt=YYYY-MM-DD`): Firehose's prefix uses the arrival timestamp; the CTAS computes `dt` from `event_ms`.
- **Partition projection** on `fleet_live` (`dt` as a date, the last 30 days): Athena computes the folders from the table's properties, so today's folder is queryable the moment Firehose writes into it, with no crawler and no `MSCK REPAIR`.
- Every query filters on `dt`.

## Alternatives considered
- **Hourly partitions:** finer pruning, but 24 times more folders and smaller files; the questions here are per day or within a day.
- **Glue crawlers:** they would need to run after every new folder, and with this account's Lake Formation settings during the build, a crawler-created table would have needed its own grants.
- **Leaving the history as JSON and only streaming new data to Parquet:** two layouts and two sets of queries forever, for a one-time migration cost of US$0.035.

## Consequences
- Measured: Q1 23.95 MB instead of 7.19 GB, Q2 40.41 MB instead of 7.19 GB, answers identical; the 7 days shrank from 7.19 GB to 458.87 MB.
- Without the `dt` filter, Q1 still scanned 23.95 MB here, because each day's files held only that day; that depends on how files are written, so the filter remains the rule.
- `dt` in `fleet_live` is the UTC arrival day, not the ping's own day: a ping that arrives just after midnight UTC lands in the next day's folder. Queries near midnight read two days.
- Firehose writes small files (230 files averaging 48 KB for the run); production needs a daily compaction.
