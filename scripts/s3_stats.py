#!/usr/bin/env python3
"""Objects under an S3 prefix: how many, how big, smallest / largest / average.

  python3 scripts/s3_stats.py --bucket "$LAKE_BUCKET" --prefix raw/json/ --label raw-json
"""
import argparse
import sys

from kit_aws import aws, write_result


def human(n):
    for unit, size in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if n >= size:
            return f"{n / size:,.2f} {unit}"
    return f"{n} B"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--list", type=int, default=3, help="keys to print")
    a = ap.parse_args()
    objs = aws("s3api", "list-objects-v2", "--bucket", a.bucket, "--prefix", a.prefix).get("Contents", []) or []
    sizes = [o["Size"] for o in objs]
    total = sum(sizes)
    folders = sorted({o["Key"][len(a.prefix):].split("/")[0] for o in objs if "/" in o["Key"][len(a.prefix):]})
    for o in objs[:a.list]:
        print(f"  {o['Key']}  {human(o['Size'])}")
    if len(objs) > a.list:
        print(f"  ... {len(objs) - a.list} more")
    res = {"bucket": "<lake bucket>", "prefix": a.prefix, "objects": len(objs), "total_bytes": total,
           "total": human(total), "avg_bytes": round(total / len(objs)) if objs else 0,
           "min_bytes": min(sizes, default=0), "max_bytes": max(sizes, default=0), "folders": folders}
    write_result(f"s3-{a.label}", res)
    print(f"RESULT s3 {a.label}: {len(objs)} objects, {human(total)} total, average {human(res['avg_bytes'])}, "
          f"smallest {human(res['min_bytes'])}, largest {human(res['max_bytes'])}"
          + (f", folders: {', '.join(folders)}" if folders else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
