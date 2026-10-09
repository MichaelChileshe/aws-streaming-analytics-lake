#!/usr/bin/env python3
"""Regenerates docs/architecture.svg + docs/architecture.png using the OFFICIAL AWS Architecture Icons.

The icon pack is not committed (AWS licenses it for diagrams, not redistribution). Download it from
https://aws.amazon.com/architecture/icons/, unzip, then:

    AWS_ICONS_DIR=/path/to/unzipped-icon-package python3 build_architecture.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from awsdiag import Diagram, GREY, INK

STREAM, LAKE, ALERT, GOV, QUERY, IAC, SIM, DENY = ("#8C4FFF", "#3F8624", "#E7157B", "#D13212", "#2E73B8",
                                                   "#7B42BC", "#7D8998", "#D13212")
d = Diagram(1900, 1200)
d.text(40, 40, "Streaming analytics lake: from an hourly JSON export to a live stream, a Parquet lake and column-level "
               "access, built and destroyed with Terraform", 19, "bold")
d.text(40, 64, "Mvelaphanda Logistics fleet telemetry  ·  300 trucks, one GPS ping every 5 s  ·  us-east-1  ·  every resource "
               "declared in Terraform, state in S3 with native locking", 13, "normal", GREY)


def node(key, x, y, title, lines=(), color=INK, size=44):
    d.icon(key, x, y, size)
    d.text(x + size + 10, y + 15, title, 12.5, "bold", color)
    for i, l in enumerate(lines):
        d.text(x + size + 10, y + 32 + i * 15, l, 11, "normal", GREY)


# ---------------------------------------------------------------- Terraform on my machine
d.box(40, 100, 300, 300, IAC, fill="#F7F2FC", dashed=False)
d.text(56, 126, "My machine (WSL)", 13.5, "bold", IAC)
d.text(56, 150, "terraform plan / apply / destroy", 12, "bold", INK)
d.text(56, 168, "bootstrap/  infra/", 11, "normal", GREY)
d.text(56, 186, "phase switches: infra/phases.auto.tfvars", 11, "normal", GREY)
d.text(56, 214, "quality gates before any apply:", 12, "bold", INK)
d.text(56, 232, "fmt · validate · tflint · checkov", 11, "normal", GREY)
d.text(56, 260, "the drills run as commands:", 12, "bold", INK)
d.text(56, 278, "fleet-sim · fleet-backfill · fleet-ctl (SSM)", 11, "normal", GREY)
d.text(56, 296, "athena_run · lf_check · freshness", 11, "normal", GREY)
d.text(56, 324, "account-wide Lake Formation settings:", 12, "bold", GOV)
d.text(56, 342, "snapshot before, state rm before destroy,", 11, "normal", GREY)
d.text(56, 360, "restore + diff after (scripts/lf_settings.py)", 11, "normal", GREY)

# people
d.box(40, 760, 300, 360, QUERY, fill="#F2F7FC", dashed=False)
d.text(56, 786, "Who reads the lake", 13.5, "bold", QUERY)
node("user", 56, 806, "Engineer (Michael-admin)", ["data lake administrator", "every column, mvela-engineering"], QUERY, 40)
node("iam_role", 56, 886, "mvela-ops-analyst (role)", ["10 non-personal columns only,", "mvela-analysts (1 GB/query),",
                                                       "no S3 permission on the lake"], QUERY, 40)
node("quick", 56, 990, "Amazon Quick Sight", ["same 10 columns as the analyst,", "through Athena (trial, then",
                                              "unsubscribed the same day)"], QUERY, 40)

d.group("cloud", 370, 90, 1100, 1090, "AWS Cloud")
node("s3_bucket", 400, 136, "nkosi-tfstate-(account id)", ["Terraform state, key aws-streaming-analytics-lake/",
                                                         "S3-native lock file (use_lockfile)"], IAC, 40)
d.line([(340, 156), (396, 156)], IAC, width=2)

# ---------------------------------------------------------------- us-east-1
d.group("region", 390, 210, 1060, 950, "us-east-1")

# simulator
d.group("vpc", 410, 255, 400, 230, "mvela-lake-vpc 10.130.0.0/16")
d.group("public", 425, 300, 370, 170, "public-a (us-east-1a)")
node("ec2_instance", 440, 340, "mvela-fleet-sim  c7i.large", ["fleet-sim: 60 pings/s, key = truck_id",
                                                            "fleet-backfill: 7 days of hourly JSON",
                                                            "fleet-ctl replay · no inbound, SSM only"], SIM)
node("vpc_endpoints", 440, 420, "S3 gateway endpoint", [], SIM, 32)
node("ssm", 850, 250, "SSM Run Command", ["commands from WSL, no SSH"], SIM, 36)
node("s3_bucket", 850, 316, "mvela-lake-code-(account id)", ["app/*.py uploaded by Terraform"], SIM, 36)
d.line([(340, 290), (360, 290), (360, 240), (840, 240), (840, 268), (846, 268)], SIM, dashed=True, width=1.4)

# stream
node("kinesis_streams", 440, 540, "mvela-fleet-pings", ["Kinesis Data Streams, provisioned",
                                                       "2 shards · 24 h retention · KMS"], STREAM, 48)
d.line([(462, 388), (462, 404)], STREAM, width=1)
d.line([(430, 380), (420, 380), (420, 562), (436, 562)], STREAM, width=2.4)
d.label(426, 520, "PutRecords", STREAM, 10)

# alerts
node("lambda_fn", 850, 520, "mvela-speed-alerts (python3.13, arm64)", ["speeding > 80 km/h, truck only (no driver)",
                                                                      "polling, then enhanced fan-out consumer",
                                                                      "EMF metric PingToAlertLatency"], ALERT, 40)
d.line([(700, 556), (846, 556)], ALERT, width=2.2)
d.label(640, 538, "polling → enhanced fan-out", ALERT, 10)
node("cloudwatch", 850, 612, "CloudWatch", ["alarms: lake freshness > 300 s,", "alert IteratorAge > 60 s"], INK, 40)
d.line([(870, 564), (870, 608)], ALERT, dashed=True, width=1.4)

# firehose -> lake
node("firehose", 440, 680, "mvela-fleet-to-lake", ["Amazon Data Firehose", "JSON → Parquet (Snappy) via Glue schema",
                                                   "buffer 60 s · dt=YYYY-MM-DD/"], LAKE, 48)
d.line([(464, 592), (464, 676)], LAKE, width=2.2)

d.box(420, 830, 400, 200, LAKE, fill="#F4F9EF", dashed=False)
node("s3_bucket", 436, 846, "mvela-fleet-lake-(account id)", ["raw/json/  168 hourly files, 7.19 GB (unregistered)",
                                                            "curated/fleet_live/  Firehose Parquet",
                                                            "curated/fleet_history/  7 days, 458.87 MB",
                                                            "errors/  (stayed empty)"], LAKE, 40)
d.line([(464, 732), (464, 842)], LAKE, width=2.2)
d.line([(460, 466), (460, 476), (400, 476), (400, 880), (432, 880)], SIM, dashed=True, width=1.4)
d.label(404, 790, "backfill PUT via endpoint", SIM, 10)
d.text(436, 990, "SSE-S3 · TLS-only policy · public access blocked", 11, "normal", GREY)
d.text(436, 1008, "results bucket: one prefix per workgroup, 7-day expiry", 11, "normal", GREY)

# catalog + governance
node("glue_catalog", 850, 700, "Glue Data Catalog: mvela_fleet", ["raw_pings_json (JSON, no partitions)",
                                                                  "fleet_live (Parquet, projection on dt)",
                                                                  "fleet_history (Parquet, made by CTAS)"], QUERY, 40)
d.line([(782, 712), (846, 718)], QUERY, dashed=True, width=1.4)
node("lake_formation", 860, 830, "Lake Formation", ["curated/ registered (own role),",
                                                    "vends credentials for it",
                                                    "admins = me; new DBs LF-only",
                                                    "analyst + Quick Sight: 10 columns",
                                                    "Firehose: DESCRIBE + SELECT"], GOV, 44)
d.line([(856, 852), (824, 852)], GOV, width=2)

# athena
node("athena", 1180, 830, "Athena workgroups", ["engineering: 20 GB/query",
                                                "analysts: 1 GB/query",
                                                "migration: CTAS, not enforced",
                                                "asks Lake Formation per column"], QUERY, 44)
d.line([(1192, 878), (1192, 1060), (640, 1060), (640, 1034)], QUERY, width=1.8)
d.label(900, 1050, "CTAS: raw JSON → fleet_history", QUERY, 10)
d.line([(340, 1110), (1216, 1110), (1216, 882)], QUERY, width=1.8)
d.label(760, 1100, "queries (IAM: which workgroup; Lake Formation: which columns)", QUERY, 10)

# ---------------------------------------------------------------- measured panel
bx, by = 1490, 90
d.box(bx, by, 390, 1090, "#D5DBDB", fill="#fff", dashed=False)
d.text(bx + 14, by + 26, "Measured (one build, 9 October 2026)", 14, "bold")
res = [
    ("Same question, raw JSON vs Parquet lake", QUERY, ["Q1 day summary: 7.19 GB → 23.95 MB", "US$0.035094 → US$0.000114 (307x less)",
                                                       "Q2 one truck 15 min: 7.19 GB → 40.41 MB",
                                                       "answers identical: 300, 300, 180 rows"]),
    ("Migration (one CTAS)", LAKE, ["7.19 GB JSON → 458.87 MB Parquet (~16x)", "210 files, 7 partitions x 5,184,000 pings"]),
    ("Stream", STREAM, ["3,600 records/min, 0 throttled", "414,660 pings in 6,910 s, 0 lost",
                        "shards (5 min): 8,493 and 7,050"]),
    ("Speeding alerts, ping → function", ALERT, ["polling: p50 763 / p99 866 ms", "enhanced fan-out: p50 79 / p99 181 ms",
                                                "0 errors · no driver fields in alerts"]),
    ("Lake freshness", LAKE, ["Firehose DataFreshness max 70-74 s", "newest row in Athena 10.3-41.3 s behind",
                              "0 failed conversions, 0 error files"]),
    ("Replay from the stream", STREAM, ["MV-0042, 10 min: 37,800 records read,", "120 pings · the lake: 120, max 82.5 km/h"]),
    ("Lake Formation", GOV, ["8 of 8 access checks as expected:", "analyst: driver_phone COLUMN_NOT_FOUND,",
                             "raw table TABLE_NOT_FOUND, S3 denied"]),
    ("Terraform", IAC, ["60 + 1 + 1 resources; EFO 2 / 1 / 1", "Destroy complete! 62 destroyed",
                        "LF settings restored: identical"]),
]
y = by + 58
for title, c, ls in res:
    d.text(bx + 14, y, title, 12, "bold", c)
    for l in ls:
        y += 16
        d.text(bx + 14, y, l, 11.2)
    y += 26

here = os.path.dirname(os.path.abspath(__file__))
d.save(os.path.join(here, "..", "architecture.svg"), os.path.join(here, "..", "architecture.png"))
print("wrote docs/architecture.svg and docs/architecture.png")
