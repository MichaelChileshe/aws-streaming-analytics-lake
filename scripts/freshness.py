#!/usr/bin/env python3
"""How far behind the trucks is the lake? Every --every seconds for --minutes, ask Athena for the
newest ping in today's fleet_live folder and compare it with the clock:

  lag = (moment the query was sent) - (newest event_ms the lake can return)

Firehose writes a file every 60 s, so the lag saws between "delivery time" (just after a file
lands) and "delivery time + 60 s" (just before the next one). Also counts the Parquet files
Firehose has written today and their average size.

  python3 scripts/freshness.py --minutes 5 --every 30 --label lake-freshness
"""
import argparse
import datetime as dt
import statistics
import sys
import time

from athena_run import run_query
from kit_aws import aws, env, write_result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--every", type=int, default=30)
    ap.add_argument("--label", required=True)
    a = ap.parse_args()
    bucket = env("LAKE_BUCKET")
    polls, scanned, cost = [], 0, 0.0
    t_end = time.time() + a.minutes * 60
    print("  UTC        rows in lake   newest ping (UTC)   lag")
    while time.time() < t_end:
        t0 = time.time()
        day = dt.datetime.now(dt.timezone.utc).date().isoformat()
        sent_ms = int(time.time() * 1000)
        q = run_query(f"SELECT count(*), max(event_ms) FROM mvela_fleet.fleet_live WHERE dt = '{day}'",
                      "mvela-engineering", quiet=True, save=False)
        if q["state"] == "SUCCEEDED" and q["rows"] and q["rows"][0][1]:
            rows, newest = int(q["rows"][0][0]), int(q["rows"][0][1])
            lag = (sent_ms - newest) / 1000
            polls.append({"utc": dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S"), "rows": rows,
                          "newest_utc": dt.datetime.fromtimestamp(newest / 1000, dt.timezone.utc).strftime("%H:%M:%S"),
                          "lag_s": round(lag, 1)})
            p = polls[-1]
            print(f"  {p['utc']}   {rows:>12,}   {p['newest_utc']}            {lag:6.1f} s", flush=True)
        else:
            print(f"  {q['state']} {q.get('reason', '')} (nothing in today's folder yet?)", flush=True)
        scanned += q.get("data_scanned_bytes", 0)
        cost += q.get("cost_usd", 0.0)
        time.sleep(max(0, a.every - (time.time() - t0)))
    objs = aws("s3api", "list-objects-v2", "--bucket", bucket,
               "--prefix", f"curated/fleet_live/dt={dt.datetime.now(dt.timezone.utc).date().isoformat()}/").get("Contents", []) or []
    lags = [p["lag_s"] for p in polls]
    res = {"polls": polls, "lag_s": {"min": min(lags, default=None), "median": statistics.median(lags) if lags else None,
                                     "max": max(lags, default=None)},
           "firehose_files_today": len(objs),
           "avg_file_kb": round(sum(o["Size"] for o in objs) / len(objs) / 1024, 1) if objs else None,
           "queries": len(polls), "scanned_bytes": scanned, "cost_usd": round(cost, 6)}
    write_result(f"freshness-{a.label}", res)
    print(f"RESULT freshness {a.label}: lag min {res['lag_s']['min']} s, median {res['lag_s']['median']} s, "
          f"max {res['lag_s']['max']} s over {len(polls)} polls; Firehose files today {len(objs)}, "
          f"average {res['avg_file_kb']} KB; {len(polls)} queries cost ~US${cost:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
