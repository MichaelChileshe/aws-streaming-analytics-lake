#!/usr/bin/env python3
"""CloudWatch metrics minute by minute, times shown in UTC.

  python3 scripts/cw_metrics.py --label kinesis-in --namespace AWS/Kinesis --dim StreamName=mvela-fleet-pings \
      --minutes 10 IncomingRecords:Sum PutRecords.Latency:Average
  python3 scripts/cw_metrics.py --label alert-latency-polling --namespace Mvelaphanda/Fleet --dim Consumer=polling \
      --minutes 10 --summary PingToAlertLatency:p50,p95,p99,Maximum,SampleCount

METRIC:STAT[,STAT...]  STAT = Sum, Average, Maximum, Minimum, SampleCount or a percentile (p50, p99.9).
--summary: one figure over the whole window instead of a row per minute.
"""
import argparse
import datetime as dt
import sys

from kit_aws import aws, write_result

BASIC = {"Sum", "Average", "Maximum", "Minimum", "SampleCount"}


def _call(namespace, metric, dims, start, end, period, flag, stats):
    args = ["cloudwatch", "get-metric-statistics", "--namespace", namespace, "--metric-name", metric,
            "--start-time", start.strftime("%Y-%m-%dT%H:%M:%SZ"), "--end-time", end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "--period", str(period), flag, *stats]
    if dims:
        args += ["--dimensions", *[f"Name={k},Value={v}" for k, v in dims]]
    return aws(*args).get("Datapoints", [])


def fetch(namespace, metric, dims, stats, start, end, period):
    """CloudWatch takes either plain statistics or percentiles in one call, not both: two calls, merged."""
    basic = [s for s in stats if s in BASIC]
    ext = [s for s in stats if s not in BASIC]
    merged = {}
    for flag, group in (("--statistics", basic), ("--extended-statistics", ext)):
        if not group:
            continue
        for p in _call(namespace, metric, dims, start, end, period, flag, group):
            # The CLI may print timestamps with the local UTC offset (e.g. +02:00): convert to UTC.
            ts = p["Timestamp"]
            if isinstance(ts, (int, float)):
                t = dt.datetime.fromtimestamp(ts, dt.timezone.utc)
            else:
                t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
            vals = merged.setdefault(t, {s: None for s in stats})
            for s in group:
                vals[s] = p.get(s) if flag == "--statistics" else p.get("ExtendedStatistics", {}).get(s)
    return sorted(merged.items(), key=lambda x: x[0])


def fmt(v):
    if v is None:
        return "-"
    return f"{v:,.0f}" if abs(v) >= 100 or float(v).is_integer() else f"{v:,.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True)
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--dim", action="append", default=[], help="Name=Value (repeatable)")
    ap.add_argument("--minutes", type=int, default=10)
    ap.add_argument("--period", type=int, default=60)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("metrics", nargs="+", help="Metric:Stat[,Stat]")
    a = ap.parse_args()
    dims = [tuple(d.split("=", 1)) for d in a.dim]
    end = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    start = end - dt.timedelta(minutes=a.minutes)
    period = a.minutes * 60 if a.summary else a.period
    out = {"namespace": a.namespace, "dimensions": dict(dims), "start_utc": start.isoformat(),
           "end_utc": end.isoformat(), "period_s": period, "metrics": {}}
    print(f"{a.namespace} {dict(dims)}  {start:%Y-%m-%d %H:%M} to {end:%H:%M} UTC, period {period} s")
    for spec in a.metrics:
        metric, stats = spec.split(":", 1)
        stats = stats.split(",")
        pts = fetch(a.namespace, metric, dims, stats, start, end, period)
        out["metrics"][metric] = [{"utc": t.strftime("%H:%M"), **v} for t, v in pts]
        print(f"\n  {metric}")
        print("  UTC    " + "".join(f"{s:>14}" for s in stats))
        for t, v in pts:
            print(f"  {t:%H:%M}  " + "".join(f"{fmt(v[s]):>14}" for s in stats))
        if not pts:
            print("  (no datapoints yet: metrics arrive 1-3 minutes late; wait and run again)")
    write_result(f"cw-{a.label}", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
