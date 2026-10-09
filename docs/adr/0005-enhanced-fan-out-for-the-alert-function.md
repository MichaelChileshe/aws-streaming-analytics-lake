# 0005 · Enhanced fan-out for the alert function

**Status:** accepted · 2026-10-09

## Context
The alert function's job is latency: a speeding truck should reach the control room within seconds. In polling mode it shares each shard's 5 reads a second and 2 MB/s with Firehose, and its poller reads each shard about once a second.

## Decision
The function reads through a registered **enhanced fan-out consumer** (`mvela-speed-alerts-efo`): a dedicated 2 MB/s per shard, records pushed over HTTP/2. It's one variable (`alerts_efo`), so the same code can run either way and the two modes were measured on the same stream.

## Alternatives considered
- **Stay on polling:** under a second already, and free. Good enough for many uses; the measured difference decided it.
- **A shorter batching window or smaller batches:** they don't change how often the poller reads a shard.

## Consequences
- Measured: ping-to-function p50 763 → 79 ms, p99 866 → 181 ms; `IteratorAge` 761–869 → 109–180 ms; 0 errors in both modes.
- Cost: US$0.015 per consumer-shard-hour (about US$0.72 a day for two shards) plus US$0.013 per GB.
- Switching replaces the event source mapping. With `starting_position = "LATEST"`, pings during the changeover aren't checked; a production switch would create the new mapping at `AT_TIMESTAMP` first and remove the old one after.
- A stream supports up to 20 enhanced fan-out consumers, so more latency-sensitive readers can be added without competing for reads.
