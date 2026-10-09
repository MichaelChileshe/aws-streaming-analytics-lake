#!/usr/bin/env python3
"""Run one Athena query from a .sql file, wait for it, and record what it cost.

  python3 scripts/athena_run.py --wg mvela-engineering --label q1-json --sql sql/q1_daily_json.sql --param day=2026-10-05

{name} placeholders in the SQL are filled from --param name=value, plus {db}, {lake_bucket},
{day_start_ms} and {day_end_ms} (from day=YYYY-MM-DD). Prints the first rows, then one RESULT
line: data scanned, run time, and the cost at Athena's price (US$5 per TB scanned, at least
10 MB per query). The full result goes to build/results/athena-<label>.csv and the numbers to
build/results/athena-<label>.json.
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import time

from kit_aws import RESULTS, aws, aws_try, become, env, write_result

PRICE_PER_TB = 5.00
TB = 1024 ** 4
MIN_BYTES = 10 * 1024 * 1024


def cost(scanned):
    return max(scanned, MIN_BYTES) / TB * PRICE_PER_TB


def human(n):
    for unit, size in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if n >= size:
            return f"{n / size:,.2f} {unit}"
    return f"{n} B"


def fill(sql, params):
    p = {"db": "mvela_fleet", "lake_bucket": os.environ.get("LAKE_BUCKET", "")}
    p.update(params)
    if "day" in p:
        d0 = dt.datetime.fromisoformat(p["day"]).replace(tzinfo=dt.timezone.utc)
        p.setdefault("day_start_ms", str(int(d0.timestamp() * 1000)))
        p.setdefault("day_end_ms", str(int((d0 + dt.timedelta(days=1)).timestamp() * 1000)))
    # Full-line "--" comments are for people reading the .sql file; Athena gets the statement only.
    sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--")).strip()
    try:
        return sql.format_map(p)
    except KeyError as e:
        sys.exit(f"the SQL needs --param {e.args[0]}=...")


def run_query(sql, wg, label=None, show=5, quiet=False, save=True):
    """Run sql in workgroup wg. Returns a dict with state, reason, header, rows and the numbers."""
    t0 = time.time()
    ok, start, err = aws_try("athena", "start-query-execution", "--work-group", wg,
                             "--query-execution-context", "Database=mvela_fleet", "--query-string", sql)
    if not ok:
        out = {"label": label, "workgroup": wg, "state": "NOT_STARTED", "reason": err, "rows": [], "header": []}
        if not quiet:
            print(f"  could not start the query: {err}")
        return out
    qid = start["QueryExecutionId"]
    while True:
        q = aws("athena", "get-query-execution", "--query-execution-id", qid)["QueryExecution"]
        state = q["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    st = q.get("Statistics", {})
    scanned = int(st.get("DataScannedInBytes", 0))
    out = {"label": label, "workgroup": wg, "query_id": qid, "state": state,
           "reason": q["Status"].get("StateChangeReason", ""),
           "data_scanned_bytes": scanned, "data_scanned": human(scanned),
           "engine_ms": st.get("EngineExecutionTimeInMillis"), "total_ms": st.get("TotalExecutionTimeInMillis"),
           "statement_type": q.get("StatementType"), "cost_usd": 0.0,
           "wall_seconds": round(time.time() - t0, 1), "header": [], "rows": []}
    # Billing: failed queries are free; DML is billed per byte scanned with a 10 MB minimum;
    # a cancelled query (or a CTAS) is billed for what it scanned.
    if state == "SUCCEEDED" and q.get("StatementType") == "DML":
        out["cost_usd"] = round(cost(scanned), 6)
    elif state != "FAILED" and scanned:
        out["cost_usd"] = round(scanned / TB * PRICE_PER_TB, 6)
    if state == "SUCCEEDED" and q.get("StatementType") == "DML":
        token, first = None, True
        while True:
            args = ["athena", "get-query-results", "--query-execution-id", qid, "--max-items", "100000"]
            if token:
                args += ["--starting-token", token]
            page = aws(*args)
            rows = [[c.get("VarCharValue", "") for c in r["Data"]] for r in page["ResultSet"]["Rows"]]
            if first and rows:
                out["header"], rows = rows[0], rows[1:]
            first = False
            out["rows"] += rows
            token = page.get("NextToken")
            if not token:
                break
    out["row_count"] = len(out["rows"])
    if not quiet:
        if out["header"]:
            print("  " + " | ".join(out["header"]))
            for r in out["rows"][:show]:
                print("  " + " | ".join(r))
            if out["row_count"] > show:
                print(f"  ... {out['row_count'] - show} more rows")
        if state != "SUCCEEDED":
            print(f"  {state}: {out['reason']}")
        print(f"RESULT athena {label or ''}: {state}, scanned {out['data_scanned']} ({scanned:,} bytes), "
              f"engine {out['engine_ms']} ms, total {out['total_ms']} ms, rows {out['row_count']}, "
              f"cost ~US${out['cost_usd']:.6f}  [{wg}, {qid}]")
    if save and label:
        os.makedirs(RESULTS, exist_ok=True)
        if out["header"]:
            with open(os.path.join(RESULTS, f"athena-{label}.csv"), "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(out["header"])
                w.writerows(out["rows"])
        write_result(f"athena-{label}", {k: v for k, v in out.items() if k != "rows"} | {"sql": sql})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wg", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--sql", required=True, help="path to a .sql file")
    ap.add_argument("--param", action="append", default=[], help="name=value (repeatable)")
    ap.add_argument("--show", type=int, default=5, help="rows to print")
    ap.add_argument("--as-analyst", action="store_true", help="run as the mvela-ops-analyst role")
    ap.add_argument("--print-sql", action="store_true")
    a = ap.parse_args()
    params = dict(p.split("=", 1) for p in a.param)
    sql = fill(open(a.sql).read(), params)
    if a.print_sql:
        print(sql)
    if a.as_analyst:
        print(f"  running as {become(env('ANALYST_ROLE_ARN'))}")
    out = run_query(sql, a.wg, a.label, show=a.show)
    return 0 if out["state"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    sys.exit(main())
