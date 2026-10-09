# Cost model

Built and destroyed on 9 October 2026. The stream ran for 6,910 s (just under two hours); the simulator and the shards existed for about three hours in all, from the first apply to the destroy. The figures below are my estimate from AWS's us-east-1 list prices. When I packaged the repo, Cost Explorer's daily view for 7 to 9 October showed only 7 October (an earlier project's build day), so the build day hadn't posted yet; I'll replace the estimate with the actual figure once it has.

| Item | Usage | Estimate (US$) |
|---|---|---|
| Simulator | c7i.large ~US$0.089/hour + public IPv4 US$0.005/hour, ~3 hours | ~0.28 |
| Kinesis data stream | 2 shards × US$0.015 per shard-hour × ~3 hours; 414,660 PUT payload units at US$0.014 per million; 2 shard-level metrics | ~0.10 |
| Enhanced fan-out | 1 consumer × 2 shards × US$0.015 per consumer-shard-hour, from 05:50 UTC to the destroy (~2 hours); data retrieval US$0.013 per GB (well under 0.1 GB) | ~0.06 |
| Firehose | every record billed as at least 5 KB: 414,660 × 5 KB ≈ 2.1 GB × US$0.029, plus format conversion at US$0.018 per GB | ≤ 0.10 |
| Athena | three full scans of the 7.19 GB export (Q1, Q2, the CTAS) at US$0.035094 each = 0.105; about 30 small queries at the 10 MB minimum | ~0.11 |
| S3 | ~8 GB for a few hours; about a thousand PUTs (168 + 210 + 230 data files, query results); Athena's GETs | ~0.01 |
| Lambda | ~14,000 invocations of ~2.3 ms at 256 MB, arm64 | < 0.01 |
| CloudWatch | EMF log lines from the function, 10 custom metric series for a few hours, 2 alarms | ~0.02 |
| Glue Data Catalog, Lake Formation, KMS (`aws/kinesis`), the S3 gateway endpoint | within free tiers or free | 0.00 |
| Amazon Quick Sight | free trial, cancelled the same day | 0.00 |
| **Total** | | **≈ 0.70** (budgeted US$1–2) |

**What keeps costing after the destroy:** the shared Terraform state bucket (an empty 610-byte state file for this project): well under US$0.01 a month. The custom metrics in `Mvelaphanda/Fleet` can't be deleted; they're only billed while data is being published, and they expire on their own. The Glue `default` database and Quick Sight's IAM service roles are free.

**Cost lessons from the build:**

- **On a flat JSON folder, every question costs the whole folder.** Each of Q1 and Q2 cost US$0.035094 on the export and US$0.000114 / US$0.000193 on Parquet. A dashboard refreshing Q2 every 5 minutes for a month (8,640 runs) would be about US$303 on the export and about US$1.67 on the lake, and the export's cost grows every day the folder does.
- **The migration paid for itself on the second query.** The CTAS cost the same as one query on the export (it reads it once).
- **Firehose's 5 KB minimum is the biggest line for small records.** A ping is about 200 bytes but bills as 5 KB, 25 times its size. If volume grew, batching several pings into one record at the producer would cut it.
- **Enhanced fan-out is billed by the hour whether or not it's used,** about US$0.72 a day for one consumer on two shards. Worth it for the alert path; not for a reader that's happy to wait a second.
- **A scan limit is a cost control.** The analysts workgroup cancels any query over 1 GB, so the most a mistaken analyst query can cost is about half a cent.
