#!/usr/bin/env python3
"""Who can see what: the Lake Formation access matrix, tested with real queries.

First as me (Michael-admin, engineering): the personal columns ARE in the lake.
Then as mvela-ops-analyst (assumed role, mvela-analysts workgroup):
  1 depot summary from fleet_live                       expect: works
  2 truck_id + driver_phone from fleet_live             expect: refused (column not visible)
  3 SELECT * from fleet_live                            expect: no driver_* columns in the result
  4 fleet_history per day                               expect: works (7 days)
  5 the raw JSON export                                 expect: refused (no Lake Formation grant)
  6 a query in the mvela-engineering workgroup          expect: refused by IAM
  7 list the lake bucket directly with S3               expect: AccessDenied (no S3 permissions)

  python3 scripts/lf_check.py --day 2026-10-07
"""
import argparse
import datetime as dt
import re
import sys

from athena_run import run_query
from kit_aws import aws_try, become, env, write_result

PII = {"driver_id", "driver_phone"}
DENIED_COLUMN = r"COLUMN_NOT_FOUND|cannot be resolved|Insufficient Lake Formation|AccessDenied|not authorized"
DENIED_TABLE = r"TABLE_NOT_FOUND|does not exist|not found|Insufficient Lake Formation|AccessDenied|not authorized"


def athena(sql, wg, label):
    q = run_query(sql, wg, label=label, show=3)
    return q


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--day", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    a = ap.parse_args()
    bucket, role = env("LAKE_BUCKET"), env("ANALYST_ROLE_ARN")
    live = f"mvela_fleet.fleet_live WHERE dt = '{a.day}'"
    checks = []

    def record(n, what, expect, passed, detail):
        checks.append({"n": n, "check": what, "expected": expect, "pass": passed, "detail": detail[:300]})
        print(f"  -> {'PASS' if passed else 'FAIL'}  ({detail[:200]})\n", flush=True)

    print("[0] as me, engineering workgroup: the personal columns exist")
    q = athena(f"SELECT truck_id, driver_id, driver_phone FROM {live} LIMIT 3", "mvela-engineering", "lf-0-engineer-pii")
    record(0, "engineer reads driver columns", "works", q["state"] == "SUCCEEDED" and q["row_count"] > 0,
           f"{q['state']}, columns {q['header']}")

    print(f"switching identity: {become(role)}\n")

    print("[1] analyst: depot summary from fleet_live")
    q = athena(f"SELECT depot, count(*) AS pings, round(avg(speed_kmh), 1) AS avg_kmh FROM {live} GROUP BY depot ORDER BY depot",
               "mvela-analysts", "lf-1-analyst-summary")
    record(1, "analyst depot summary", "works", q["state"] == "SUCCEEDED" and q["row_count"] > 0,
           f"{q['state']}, {q['row_count']} rows, scanned {q.get('data_scanned')}")

    print("[2] analyst: truck_id + driver_phone")
    q = athena(f"SELECT truck_id, driver_phone FROM {live} LIMIT 3", "mvela-analysts", "lf-2-analyst-pii")
    record(2, "analyst asks for driver_phone", "refused (column hidden)",
           q["state"] == "FAILED" and re.search(DENIED_COLUMN, q["reason"], re.I) is not None,
           f"{q['state']}: {q['reason']}")

    print("[3] analyst: SELECT *")
    q = athena(f"SELECT * FROM {live} LIMIT 3", "mvela-analysts", "lf-3-analyst-star")
    hidden = not (PII & set(q["header"]))
    record(3, "analyst SELECT * hides driver columns", "10 columns, no driver_*",
           q["state"] == "SUCCEEDED" and q["row_count"] > 0 and hidden and "dt" in q["header"] and len(q["header"]) == 10,
           f"{q['state']}, {len(q['header'])} columns returned {q['header']} {q['reason']}")

    print("[4] analyst: fleet_history per day")
    q = athena("SELECT dt, count(*) AS pings FROM mvela_fleet.fleet_history GROUP BY dt ORDER BY dt",
               "mvela-analysts", "lf-4-analyst-history")
    record(4, "analyst reads fleet_history", "works", q["state"] == "SUCCEEDED" and q["row_count"] > 0,
           f"{q['state']}, {q['row_count']} days, scanned {q.get('data_scanned')} {q['reason']}")

    print("[5] analyst: the raw JSON export")
    q = athena("SELECT truck_id FROM mvela_fleet.raw_pings_json LIMIT 1", "mvela-analysts", "lf-5-analyst-raw")
    record(5, "analyst reads raw_pings_json", "refused (no LF grant)",
           q["state"] == "FAILED" and re.search(DENIED_TABLE, q["reason"], re.I) is not None,
           f"{q['state']}: {q['reason']}")

    print("[6] analyst: a query in the engineering workgroup")
    q = run_query("SELECT 1", "mvela-engineering", label="lf-6-analyst-engineering-wg", show=1)
    record(6, "analyst uses mvela-engineering", "refused by IAM", q["state"] == "NOT_STARTED" and "AccessDenied" in q["reason"],
           f"{q['state']}: {q['reason']}")

    print("[7] analyst: list the lake bucket with S3 directly")
    ok, _, err = aws_try("s3api", "list-objects-v2", "--bucket", bucket, "--prefix", "curated/fleet_live/", "--max-items", "1")
    record(7, "analyst lists the lake in S3", "AccessDenied", (not ok) and "AccessDenied" in err,
           "listed objects!" if ok else err.replace(bucket, "<lake bucket>"))

    passed = sum(c["pass"] for c in checks)
    write_result("lf-check", {"day": a.day, "analyst_role": "mvela-ops-analyst", "checks": checks,
                              "passed": passed, "total": len(checks)})
    print("  #  check                                         expected                          result")
    for c in checks:
        print(f"  {c['n']}  {c['check']:<45} {c['expected']:<33} {'PASS' if c['pass'] else 'FAIL'}")
    print(f"RESULT lf-check: {passed} of {len(checks)} as expected")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
