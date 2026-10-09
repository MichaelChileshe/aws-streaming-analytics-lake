# 0001 · A provisioned Kinesis data stream as the entry point, with Firehose and Lambda as independent readers

**Status:** accepted · 2026-10-09

## Context
The fleet's GPS readings arrived once an hour as a JSON file. Three consumers need them, at three different speeds: the control room's speeding alerts (seconds), the analytics lake (minutes, in efficient files), and occasional look-backs at what a truck just did. Writing to S3 directly would serve only the lake; sending to Firehose directly would serve the lake and nothing else, because Firehose keeps nothing once delivered.

## Decision
- Every ping goes into one **Kinesis data stream** (`mvela-fleet-pings`), partition key `truck_id`, so one truck's pings stay in order on one shard.
- **Provisioned mode, 2 shards, 24-hour retention**, encrypted with the AWS managed key. The fleet sends 60 records a second (about 12 KB/s); two shards take 2,000 records or 2 MB a second.
- **Two independent readers:** Firehose (to Parquet in S3) and a Lambda function (alerts). Any other reader, such as a replay, reads the stream at its own position without affecting them.

## Alternatives considered
- **On-demand mode:** no shard planning, but billed per stream-hour plus per GB; for a small, steady 60 records a second, two provisioned shards are cheaper and the load is predictable.
- **Firehose with Direct PUT:** simpler, but no alerts in seconds and no replay.
- **Amazon MSK:** a Kafka cluster to run for 60 records a second; far more than this needs.

## Consequences
- Measured: 3,600 records a minute, 0 throttled; 414,660 sent and 414,660 delivered by Firehose; replay found 120 of 120 pings for one truck from the stream.
- Two readers share each shard's 5 reads a second and 2 MB/s in polling mode; more readers would compete, which is what enhanced fan-out is for ([0005](0005-enhanced-fan-out-for-the-alert-function.md)).
- Shards are billed by the hour whether or not data flows.
