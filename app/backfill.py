"""fleet-backfill: the legacy history. Writes the telematics vendor's hourly JSON export for the
last N full days (UTC) into ONE flat S3 prefix, exactly the way the data team stored it before
the lake: no partitions, no compression, one JSON object per line.

  fleet-backfill --days 7            # 7 days x 300 trucks x 1 ping / 5 s = 36,288,000 pings
  fleet-backfill --days 1 --dry-run  # generate one day, upload nothing (speed check)

Each worker process builds whole days in order (trucks leave the depot in the morning, drive
their shift, park at night), so a truck's track is continuous within a day.
"""
import argparse
import datetime as dt
import sys
import time
from multiprocessing import Pool

from common import client, conf
from fleet import PING_SECONDS, make_fleet, shift_hours


def day_list(days):
    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return [(today - dt.timedelta(days=d)).date().isoformat() for d in range(days, 0, -1)]


def build_day(job):
    """Generate one UTC day; upload it as 24 hourly files. Returns (day, rows, bytes, seconds)."""
    day, dry_run, settings = job
    t0 = time.time()
    day0 = dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc)
    day0_ms = int(day0.timestamp() * 1000)
    salt = int(day.replace("-", ""))
    fleet = make_fleet(salt=salt)
    shifts = [shift_hours(i, salt) for i in range(len(fleet))]
    s3 = None if dry_run else client("s3", settings["REGION"])
    home = [False] * len(fleet)                       # parked back at the depot after the shift
    rows = nbytes = 0
    for hour in range(24):
        lines = []
        for tick in range(hour * 3600, (hour + 1) * 3600, PING_SECONDS):
            h = tick / 3600.0
            for i, truck in enumerate(fleet):
                start, end = shifts[i]
                on_shift = start <= h < end
                if h >= end and not home[i]:
                    truck.park_at_depot()             # end of shift: back at the depot overnight
                    home[i] = True
                truck.step(on_shift)
                lines.append(truck.json(day0_ms + tick * 1000 + truck.offset_ms, on_shift))
        body = ("\n".join(lines) + "\n").encode()
        rows += len(lines)
        nbytes += len(body)
        if s3:
            key = f"{settings['RAW_PREFIX']}fleet-export-{day}T{hour:02d}.json"
            s3.put_object(Bucket=settings["LAKE_BUCKET"], Key=key, Body=body, ContentType="application/x-ndjson")
    return day, rows, nbytes, time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    settings = conf()
    days = day_list(a.days)
    where = "nowhere (dry run)" if a.dry_run else f"s3://{settings['LAKE_BUCKET']}/{settings['RAW_PREFIX']}"
    print(f"generating {len(days)} day(s) {days[0]} .. {days[-1]} -> {where}", flush=True)
    t0 = time.time()
    total_rows = total_bytes = 0
    with Pool(a.workers) as pool:
        for day, rows, nbytes, secs in pool.imap(build_day, [(d, a.dry_run, settings) for d in days]):
            total_rows += rows
            total_bytes += nbytes
            print(f"  {day}: {rows:,} pings, {nbytes / 1e6:,.1f} MB in 24 hourly files ({secs:.0f} s)", flush=True)
    secs = time.time() - t0
    print(f"RESULT backfill: {total_rows:,} pings, {total_bytes / 1e9:.2f} GB of JSON, "
          f"{len(days) * 24} files, {secs:.0f} s ({total_rows / secs:,.0f} pings/s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
