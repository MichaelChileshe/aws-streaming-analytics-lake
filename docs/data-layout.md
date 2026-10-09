# Data layout: the same questions on raw JSON and on the Parquet lake

## The "before": one flat folder of hourly JSON

`fleet-backfill` wrote the last 7 full UTC days (2 to 8 October 2026) exactly as the vendor delivered them and the data team stored them: one uncompressed JSON file per hour, all in `raw/json/`, no partitions.

| | Measured |
|---|---|
| Pings | **36,288,000** (300 trucks × one every 5 s × 7 days); 5,184,000 per day |
| Files | **168**, 43.79–43.83 MB each |
| Size | **7.19 GB** in S3 (the backfill reports the same bytes as 7.72 GB because it counts 1 GB = 10⁹ bytes; the scripts count 1,024³) |
| Generated in | 108 s on the c7i.large, through the S3 gateway endpoint |

Each ping is one JSON object with 11 fields, `driver_id` and `driver_phone` included. Screenshot [`11`](screenshots/11-backfill-7-days-raw-json.png).

## Two everyday questions

- **Q1:** one day's driving summary per truck (pings, top speed, average speed, seconds over 80 km/h). 300 rows.
- **Q2:** where was MV-0042 between 10:00 and 10:15 SAST that day? 180 rows out of 36 million.

The day was 7 October 2026 (`DAY`, a full day inside the history).

## The migration: one CTAS

[`sql/ctas_history.sql`](../sql/ctas_history.sql) reads the export once and writes it back as Parquet (Snappy) into `curated/fleet_history/`, partitioned by `dt` (the UTC day computed from `event_ms`). CTAS also registers the table and its 7 partitions in the Glue catalog. It ran in the `mvela-migration` workgroup: a CTAS that sets `external_location` is refused by a workgroup that enforces its own settings ([ADR 0004](adr/0004-separate-athena-workgroups-with-scan-limits.md)).

| | Raw JSON | fleet_history (Parquet) |
|---|---|---|
| Objects | 168 | 210 (several per day) |
| Total | 7,717,117,543 bytes (7.19 GB) | 481,163,795 bytes (**458.87 MB**, about 16 times smaller) |
| Bytes per ping | about 213 | about 13 |
| Partitions | none | 7 (`dt=2026-10-02` … `dt=2026-10-08`), 5,184,000 pings and 300 trucks each |

The CTAS scanned 7.19 GB once (engine 9,646 ms, US$0.035094). Counting pings per day afterwards scanned 4.34 MB. Screenshot [`13`](screenshots/13-ctas-migration-and-history-partitions.png).

## The comparison

All in the `mvela-engineering` workgroup. Cost is Athena's US$5 per TB scanned, as the script computes it.

| Query | Format | Day filter | Scanned | Engine ms | Cost (US$) | Rows |
|---|---|---|---|---|---|---|
| Q1 | raw JSON | (none possible) | 7,717,247,824 B (7.19 GB) | 1,665 | 0.035094 | 300 |
| Q1 | Parquet | `dt = '2026-10-07'` | 25,117,150 B (**23.95 MB**) | 1,298 | 0.000114 | 300 |
| Q1 | Parquet | none | 25,117,150 B (23.95 MB) | 2,072 | 0.000114 | 300 |
| Q2 | raw JSON | (none possible) | 7,717,199,675 B (7.19 GB) | 2,660 | 0.035094 | 180 |
| Q2 | Parquet | `dt = '2026-10-07'` | 42,371,165 B (**40.41 MB**) | 1,163 | 0.000193 | 180 |

[`scripts/compare_results.py`](../scripts/compare_results.py) compared each Parquet answer with the JSON one, row by row: **identical, 300 rows × 5 columns** (twice) and **identical, 180 rows × 6 columns**. Screenshots [`12`](screenshots/12-q1-q2-on-raw-json.png), [`15`](screenshots/15-q1-parquet-with-and-without-dt.png), [`16`](screenshots/16-q2-parquet-and-identical-answers.png); data in [`results/athena-json-vs-parquet.csv`](results/athena-json-vs-parquet.csv).

## What the numbers taught me

**On JSON, a `WHERE` clause saves nothing.** Q2 wanted 180 rows and paid for 36 million: Athena had to read every byte of every file to find them. That is the bill the data team kept getting, and it grows with the folder.

**Q2 reads more than Q1 on Parquet.** Q1 uses 3 columns (`truck_id`, `speed_kmh`, `event_ms`); Q2 uses 6, including the two `double` coordinates. And every file holds every truck, so filtering on one truck can't skip blocks the way filtering on time can. If "one truck's track" became the main question, sorting or bucketing the files by `truck_id` would be the next step.

**Forgetting the partition filter didn't cost anything here, by luck of the layout.** Q1 without `dt` scanned exactly the same 25,117,150 bytes. Parquet stores the minimum and maximum of each column per block, and the CTAS wrote each day into its own files, so every other day's `event_ms` range rules its blocks out; the identical byte count is consistent with Athena skipping them after reading their footers, and the extra 774 ms of engine time with opening all 7 days. Files that mixed days would have been read in full, so the partition filter stays in every query I write.

**Small files are the next problem.** Firehose wrote two Parquet files per 60-second buffer: **230 files averaging 48 KB** for the 414,660 live pings, about 27 bytes per ping against 13 in the CTAS output. A day of that would be about 2,880 files. Every file is a request and a footer to read, so the fix is a nightly compaction (the same CTAS / `INSERT INTO` pattern per day) or a longer Firehose buffer if minutes of extra delay are acceptable.
