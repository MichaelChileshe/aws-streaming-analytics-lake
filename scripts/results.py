#!/usr/bin/env python3
"""Every measured number from build/results/ in one list (and build/results/summary.csv).
Run it at the end; anything not measured yet shows as "-".

  python3 scripts/results.py
"""
import csv
import json
import os
import re
import sys

from kit_aws import RESULTS


def j(name):
    p = os.path.join(RESULTS, f"{name}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def result_line(txt, prefix):
    p = os.path.join(RESULTS, txt)
    if not os.path.exists(p):
        return None
    for line in open(p, errors="replace"):
        if line.startswith(f"RESULT {prefix}"):
            return line.strip()[len("RESULT "):]
    return None


def g(d, *path):
    for k in path:
        if d is None:
            return None
        d = d.get(k) if isinstance(d, dict) else None
    return d


def main():
    rows = []

    def add(section, item, value):
        rows.append((section, item, "-" if value in (None, "") else value))

    for label, title in (("q1-json", "Q1 day summary, raw JSON"), ("q1-parquet-nopart", "Q1, Parquet, no dt filter"),
                         ("q1-parquet", "Q1, Parquet + dt filter"), ("q2-json", "Q2 one truck 15 min, raw JSON"),
                         ("q2-parquet", "Q2, Parquet + dt filter"), ("ctas-history", "CTAS migration JSON->Parquet")):
        q = j(f"athena-{label}")
        add("Athena", f"{title}: scanned", g(q, "data_scanned"))
        add("Athena", f"{title}: bytes", g(q, "data_scanned_bytes"))
        add("Athena", f"{title}: engine ms", g(q, "engine_ms"))
        add("Athena", f"{title}: cost US$", g(q, "cost_usd"))
    for name in ("q1-json-vs-q1-parquet", "q1-json-vs-q1-parquet-nopart", "q2-json-vs-q2-parquet"):
        c = j(f"compare-{name}")
        add("Same answer", name, None if c is None else f"{'identical' if c['identical'] else 'DIFFERENT'}, {c['rows']} rows")
    for label in ("raw-json", "history", "live-final"):
        s = j(f"s3-{label}")
        add("S3", f"{label}: objects / total / average",
            None if s is None else f"{s['objects']} / {s['total']} / {round(s['avg_bytes'] / 1024, 1)} KB")
    add("Backfill", "history generated", result_line("backfill.txt", "backfill"))
    add("Stream", "producer totals", result_line("sim-totals.txt", ""))
    for mode in ("polling", "efo"):
        a = j(f"alerts-{mode}")
        add("Alerts", f"{mode}: alerts / speeding pings / pings read",
            None if a is None else f"{a['alerts']} / {a['speeding_pings']} / {a['pings_read']}")
        add("Alerts", f"{mode}: alert raised after ping p50 / p95 ms",
            None if a is None else f"{a['alert_ms_after_ping']['p50']} / {a['alert_ms_after_ping']['p95']}")
        m = g(j(f"cw-latency-{mode}"), "metrics", "PingToAlertLatency")
        if m:
            # summary mode can return two partial periods: keep the one with the most samples
            m = [max(m, key=lambda p: p.get("SampleCount") or 0)]
            add("Alerts", f"{mode}: PingToAlertLatency p50 / p95 / p99 / max ms (CloudWatch)",
                f"{m[0].get('p50'):.0f} / {m[0].get('p95'):.0f} / {m[0].get('p99'):.0f} / {m[0].get('Maximum'):.0f}"
                if m[0].get("p50") is not None else None)
        else:
            add("Alerts", f"{mode}: PingToAlertLatency (CloudWatch)", None)
    f = j("freshness-lake")
    add("Lake freshness", "lag min / median / max s",
        None if f is None else f"{f['lag_s']['min']} / {f['lag_s']['median']} / {f['lag_s']['max']}")
    add("Lake freshness", "Firehose files today / average KB",
        None if f is None else f"{f['firehose_files_today']} / {f['avg_file_kb']}")
    add("Replay", "stream replay", result_line("replay.txt", "replay"))
    p = os.path.join(RESULTS, "athena-replay-lake.csv")
    rows_csv = list(csv.DictReader(open(p))) if os.path.exists(p) else []
    add("Replay", "same window from the lake (pings)", rows_csv[0].get("pings") if rows_csv else None)
    lf = j("lf-check")
    add("Lake Formation", "access checks as expected", None if lf is None else f"{lf['passed']} of {lf['total']}")
    for c in (lf or {}).get("checks", []):
        add("Lake Formation", f"{c['n']} {c['check']}", f"{'PASS' if c['pass'] else 'FAIL'}: {c['detail'][:120]}")
    for name in ("tf-plan-base.txt", "tf-plan-efo.txt", "tf-plan-history.txt", "tf-destroy.txt"):
        p = os.path.join(RESULTS, name)
        line = None
        if os.path.exists(p):
            for ln in open(p, errors="replace"):
                if re.search(r"^(Plan:|Destroy complete!|Apply complete!|No changes\.)", ln.strip()):
                    line = ln.strip()
        add("Terraform", name, line)
    add("Lake Formation", "settings after restore", result_line("lf-settings-after.txt", "lf-settings"))

    width = max(len(r[1]) for r in rows)
    section = None
    for s, item, value in rows:
        if s != section:
            print(f"\n{s}")
            section = s
        print(f"  {item:<{width}}  {value}")
    with open(os.path.join(RESULTS, "summary.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["section", "item", "value"])
        w.writerows(rows)
    print(f"\nwritten: {os.path.join(RESULTS, 'summary.csv')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
