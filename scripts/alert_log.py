#!/usr/bin/env python3
"""What the speed-alert function raised in the last N minutes, read from its log.

  python3 scripts/alert_log.py --minutes 10 --label alerts-polling

Counts SPEEDING alerts per depot, the most-alerted trucks, and how long after the ping each
alert was raised (ms_after_ping, measured inside the function). Also adds up the per-batch
lines: batches, pings read, and the consumer mode they came from.
"""
import argparse
import collections
import json
import sys
import time

from kit_aws import aws, write_result

GROUP = "/aws/lambda/mvela-speed-alerts"


def events(pattern, start_ms, end_ms):
    """filter-log-events, every page (the CLI follows nextToken itself)."""
    out = aws("logs", "filter-log-events", "--log-group-name", GROUP, "--start-time", str(start_ms),
              "--end-time", str(end_ms), "--filter-pattern", pattern)
    return [e["message"] for e in out.get("events", [])]


def parse(messages):
    out = []
    for m in messages:
        try:
            out.append(json.loads(m))
        except ValueError:
            pass
    return out


def pct(values, p):
    s = sorted(values)
    return s[max(0, min(len(s) - 1, -(-len(s) * p // 100) - 1))] if s else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=int, default=10)
    ap.add_argument("--label", required=True)
    a = ap.parse_args()
    end = int(time.time() * 1000)
    start = end - a.minutes * 60000
    alerts = [x for x in parse(events('{ $.alert = "SPEEDING" }', start, end)) if x.get("alert") == "SPEEDING"]
    batches = [x for x in parse(events("{ $.batch > 0 }", start, end)) if "batch" in x]
    by_depot = collections.Counter(x["depot"] for x in alerts)
    by_truck = collections.Counter(x["truck_id"] for x in alerts)
    lat = [x["ms_after_ping"] for x in alerts]
    modes = collections.Counter(b.get("consumer") for b in batches)
    res = {"minutes": a.minutes, "alerts": len(alerts), "by_depot": dict(sorted(by_depot.items())),
           "top_trucks": by_truck.most_common(5), "trucks_alerted": len(by_truck),
           "alert_ms_after_ping": {"p50": pct(lat, 50), "p95": pct(lat, 95), "max": max(lat, default=None)},
           "batches": len(batches), "pings_read": sum(b.get("batch", 0) for b in batches),
           "speeding_pings": sum(b.get("speeding", 0) for b in batches), "consumer_modes": dict(modes),
           "personal_fields_in_alerts": sorted({k for x in alerts for k in x if k.startswith("driver")})}
    for x in alerts[:3]:
        print("  " + json.dumps(x))
    write_result(f"alerts-{a.label}", res)
    print(f"RESULT alerts {a.label}: {res['alerts']} alerts from {res['speeding_pings']:,} speeding pings "
          f"({res['pings_read']:,} pings read in {res['batches']} batches, consumer {dict(modes)}); "
          f"by depot {res['by_depot']}; alert raised p50 {res['alert_ms_after_ping']['p50']} ms / "
          f"p95 {res['alert_ms_after_ping']['p95']} ms after the ping; driver fields in alerts: "
          f"{res['personal_fields_in_alerts'] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
