# Replay: "where was truck 42 a quarter of an hour ago?"

A dispatcher asks for MV-0042's exact track over a 10-minute window that started 15 minutes ago. The stream keeps every record for its retention period (24 hours here), and any reader can go back and read it again without moving the other readers' positions. Firehose can't do that: it delivers once and keeps nothing.

`fleet-ctl replay` ([`app/ctl.py`](../app/ctl.py)) opens every shard with an `AT_TIMESTAMP` iterator at the window's start, reads forward to the end of the window (plus a 30-second grace period), and keeps one truck's pings. Then [`sql/replay_lake.sql`](../sql/replay_lake.sql) asks the lake for the same window.

| | Stream replay | The lake (Athena) |
|---|---|---|
| Window | 06:12:58 to 06:22:58 UTC, 9 October 2026 | same |
| Records read | 18,900 per shard, **37,800** in all, **4** `GetRecords` calls, 3.3 s | 110.33 KB scanned, 1,046 ms engine time |
| MV-0042's pings | **120** (10 minutes at one per 5 s) | **120** |
| First / last ping | 1791526381000 / 1791526976000 (event_ms) | 1791526381000 / 1791526976000 |
| Top speed | **82.5 km/h** (19 pings over 80; 11.0 km driven) | **82.5 km/h** |

Screenshots [`32`](screenshots/32-stream-replay-one-truck.png), [`33`](screenshots/33-replay-window-from-the-lake.png).

**What it means in practice.** The stream answers "what just happened" for the last 24 hours without waiting for Firehose and without touching the lake, and it reads the whole fleet to find one truck (37,800 records for 120). The lake answers the same question with a filter and keeps the answer for as long as the bucket does. They agreed exactly, which is what lets the control room trust either one.

The replay printed the truck's pings without the driver fields, the same rule as the alerts: the operator tools work with trucks.
