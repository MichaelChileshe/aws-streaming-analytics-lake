# The stream, the lake behind it, and the alerts

## The stream

`mvela-fleet-pings`: provisioned mode, **2 shards**, 24-hour retention, encrypted with the AWS managed key `alias/aws/kinesis`, shard-level `IncomingRecords` metric on ([`06`](screenshots/06-kinesis-stream-summary.png)). Two shards take up to 2,000 records or 2 MB a second; the fleet sends 60 records a second of about 200 bytes each, so the second shard is there for spread and headroom, not for capacity.

`fleet-sim` runs as a systemd service on the simulator. Every second it sends a fifth of the fleet (60 pings) in one `PutRecords` call, with **partition key = `truck_id`**: one truck's pings always land on the same shard, in order, while 300 different trucks spread over both. `event_ms` is stamped just before the call, so every latency measured downstream starts there.

| Measured | Value |
|---|---|
| `IncomingRecords` per full minute (05:31–05:35 UTC) | **3,600** every minute |
| `WriteProvisionedThroughputExceeded` | **0** every minute |
| `PutRecords.Latency`, average per minute | 13.58–15.27 ms |
| Per shard, 5-minute windows | 8,493 (shard 0, from 05:32) and 7,050 (shard 1, from 05:33): both shards in use; the two windows are a minute apart and include partial minutes, so they show spread, not an exact split |
| Producer totals when stopped | **414,660 sent in 6,910 s (60.0 a second), 0 refused, 0 throttled, 0 lost**, 6,911 `PutRecords` calls, p50 19.4 ms, p99 85.7 ms (client side) |

Screenshots [`17`](screenshots/17-fleet-simulator-started.png)–[`19`](screenshots/19-kinesis-records-per-shard.png), [`46`](screenshots/46-simulator-stopped-firehose-hourly.png).

## Firehose: the stream into the lake

`mvela-fleet-to-lake` reads the stream and converts each JSON ping into a Parquet row using `fleet_live`'s schema from the Glue catalog, then writes into `curated/fleet_live/dt=!{timestamp:yyyy-MM-dd}/` ([`07`](screenshots/07-firehose-parquet-and-glue-tables.png)). Format conversion needs a buffer of at least 64 MB or 60 s; at about 12 KB a second the 60-second timer always wins. Records that fail conversion would go to `errors/`.

| Minute (UTC) | Read from stream | Converted | Failed | Delivered to S3 | DataFreshness max (s) |
|---|---|---|---|---|---|
| 05:32 | 3,600 | 3,600 | 0 | 3,600 | 71 |
| 05:33 | 3,600 | 3,567 | 0 | 3,567 | 74 |
| 05:34 | 3,568 | 3,664 | 0 | 3,664 | 71 |
| 05:35 | 3,632 | 3,602 | 0 | 3,602 | 73 |
| 05:36 | 3,572 | 3,597 | 0 | 3,597 | 70 |

Over the whole run, by hour: read **213,360 + 201,300 = 414,660**, delivered **212,734 + 201,926 = 414,660**, failed conversions 0: every ping the producer sent reached the lake. `errors/` held **0 objects**. Screenshots [`20`](screenshots/20-firehose-read-and-converted.png)–[`22`](screenshots/22-first-live-parquet-files-no-errors.png), [`46`](screenshots/46-simulator-stopped-firehose-hourly.png).

## How fresh is the lake?

`fleet_live` uses partition projection, so today's folder is queryable the moment Firehose writes into it: no crawler, no `MSCK REPAIR`. [`scripts/freshness.py`](../scripts/freshness.py) asked Athena for the newest ping in today's folder every 30 s for 5 minutes and compared it with the moment the query was sent.

| UTC | Rows in the lake | Newest ping | Lag (s) |
|---|---|---|---|
| 05:41:00 | 41,342 | 05:40:42 | 11.3 |
| 05:41:28 | 43,112 | 05:40:42 | 41.3 |
| 05:41:58 | 44,941 | 05:41:43 | 10.3 |
| 05:42:28 | 46,771 | 05:41:44 | 39.3 |
| 05:42:59 | 50,370 | 05:42:43 | 10.3 |
| 05:43:28 | 50,370 | 05:42:43 | 40.3 |
| 05:43:58 | 52,169 | 05:43:42 | 11.3 |
| 05:44:28 | 53,941 | 05:43:43 | 40.3 |
| 05:44:58 | 55,769 | 05:44:43 | 10.3 |
| 05:45:29 | 57,540 | 05:44:43 | 40.3 |

**Min 10.3 s, median 25.3 s, max 41.3 s** over 10 polls, 33 Firehose files so far that day at 48.4 KB on average. The lag saws because Firehose writes once a minute: just after a write the newest row is about 10 s old, just before the next it's about 70 s old (Firehose's own `DataFreshness`, 70–74 s). My 30-second polls landed near the two ends. Screenshot [`23`](screenshots/23-lake-freshness-depot-view-alarms.png).

The control-room view (last 15 minutes per depot, [`sql/live_by_depot.sql`](../sql/live_by_depot.sql)), as the engineer, scanned 292.96 KB:

| Depot | Trucks | Pings | Avg km/h | Max km/h | Pings over 80 |
|---|---|---|---|---|---|
| BFN | 45 | 7,839 | 61.1 | 100.3 | 435 |
| JHB | 90 | 15,678 | 61.7 | 105.7 | 1,155 |
| PLK | 45 | 7,839 | 63.7 | 109.0 | 1,108 |
| PTA | 120 | 20,906 | 58.8 | 108.8 | 1,324 |

Both alarms were `OK`: `mvela-lake-freshness` (Firehose `DataFreshness` over 300 s) and `mvela-alerts-iterator-age` (the alert function more than 60 s behind). They have no actions in this lab; in production they'd notify the on-call channel through SNS.

## Speeding alerts: polling, then enhanced fan-out

`mvela-speed-alerts` (Python 3.13, arm64, batch size 500, starting at `LATEST`) raises one alert per truck per 5 minutes above 80 km/h. An alert carries the truck, depot, speed and position, never the driver. For every record it also publishes `now − event_ms` as the metric `PingToAlertLatency` (namespace `Mvelaphanda/Fleet`, dimension `Consumer`) through the embedded metric format: structured log lines that CloudWatch turns into metrics, with no `PutMetricData` calls.

**Polling** (the default): Lambda's poller asks each shard for new records, sharing the shard's 5 reads a second and 2 MB/s with every other reader (Firehose here). **Enhanced fan-out** (`alerts_efo = true`): a registered consumer, `mvela-speed-alerts-efo`, gets its own 2 MB/s per shard and the records are pushed to it over HTTP/2 (`SubscribeToShard`).

| | Polling (10 min, 05:38–05:48) | Enhanced fan-out (8 min, 06:17–06:25) |
|---|---|---|
| `PingToAlertLatency` p50 / p95 / p99 / max (CloudWatch) | **763 / 853 / 866 / 894 ms** | **79 / 128 / 181 / 228 ms** |
| Samples | 34,474 | 26,125 |
| Same from the function's own log (alerts only) | p50 763, p95 799 ms | p50 77, p95 128 ms |
| Invocations per minute | 120, every full minute | 121–126 |
| `IteratorAge` max per minute | 761–869 ms | 109–180 ms |
| Duration, average | 2.14–2.38 ms | 2.30–2.58 ms |
| Errors | 0 | 0 |
| Pings read / batches | 35,827 / 1,194 | 28,800 / 984 |
| Speeding pings / alerts | 2,665 / 190 | 2,339 / 157 |
| Driver fields in any alert | none | none |

Screenshots [`24`](screenshots/24-alerts-polling-and-latency.png)–[`31`](screenshots/31-lambda-efo-iterator-age-duration.png); data in [`results/alerts-polling-vs-efo.csv`](results/alerts-polling-vs-efo.csv).

**What it showed:**

- **Polling ran exactly 120 times a minute:** two shards, once a second each. The latency was not just higher but strikingly steady (p50 763, p99 866 ms). My reading: the simulator writes once a second and the poller reads once a second, so every ping waits about the same fixed offset between the two.
- **Enhanced fan-out cut the wait about 10 times** (p50 763 → 79 ms) because records are pushed as they arrive. It's worth paying for when the reader's latency matters or when more than a couple of readers share a stream (they'd compete for 5 reads a second per shard).
- **The switch is a replacement, with a gap.** The plan was `2 to add, 1 to change, 1 to destroy`: the consumer created, the function's `CONSUMER_MODE` updated in place, and the event source mapping replaced, the old one destroyed first ([`27`](screenshots/27-enhanced-fan-out-plan-and-apply.png)). The new mapping starts at `LATEST`, so pings that arrived during the changeover were never checked for speeding. In production I'd create the new mapping at `AT_TIMESTAMP` before removing the old one, and accept a few duplicate checks.
- **The alert counts aren't a comparison.** The windows are 10 and 8 minutes, and the one-alert-per-5-minutes memory lives in each warm function instance, so the counts depend on how instances were reused. The latency and the "no driver fields" result are what the drill measured.
