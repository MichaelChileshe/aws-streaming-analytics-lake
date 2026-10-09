"""fleet-ctl: small operator commands on mvela-fleet-sim.

  fleet-ctl show                                   settings + the stream's shards
  fleet-ctl replay --start 2026-10-07T09:00:00Z --minutes 10 --truck MV-0042
        Re-read the stream from a moment in the past (AT_TIMESTAMP on every shard) and pull out
        one truck's pings in that window. A Kinesis data stream keeps every record for its
        retention period (24 hours here), so any consumer can go back and read it again;
        Firehose can't do that: it delivers once and keeps nothing.
"""
import argparse
import json
import math
import sys
import time

from common import client, conf, parse_utc, utc


def show(settings):
    kin = client("kinesis", settings["REGION"])
    s = kin.describe_stream_summary(StreamName=settings["STREAM"])["StreamDescriptionSummary"]
    shards = kin.list_shards(StreamName=settings["STREAM"])["Shards"]
    print(json.dumps({k: settings[k] for k in sorted(settings)}, indent=1))
    print(f"stream {s['StreamName']}: {s['StreamStatus']}, mode {s['StreamModeDetails']['StreamMode']}, "
          f"{s['OpenShardCount']} open shards, retention {s['RetentionPeriodHours']} h, "
          f"encryption {s.get('EncryptionType')} ({s.get('KeyId')}), consumers {s.get('ConsumerCount', 0)}")
    for sh in shards:
        r = sh["HashKeyRange"]
        print(f"  {sh['ShardId']}  hash keys {int(r['StartingHashKey']):.3e} .. {int(r['EndingHashKey']):.3e}")


def km_between(a, b):
    """Great-circle distance between two pings, in km."""
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp, dl = p2 - p1, math.radians(b["lon"] - a["lon"])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def replay(settings, start, minutes, truck):
    kin = client("kinesis", settings["REGION"])
    stream = settings["STREAM"]
    t_from = parse_utc(start)
    from_ms = int(t_from.timestamp() * 1000)
    to_ms = from_ms + int(minutes * 60000)
    print(f"replaying {stream} from {utc(from_ms)} to {utc(to_ms)}, looking for {truck}", flush=True)
    t0 = time.time()
    scanned, calls, mine = 0, 0, []
    for sh in kin.list_shards(StreamName=stream)["Shards"]:
        it = kin.get_shard_iterator(StreamName=stream, ShardId=sh["ShardId"],
                                    ShardIteratorType="AT_TIMESTAMP", Timestamp=t_from)["ShardIterator"]
        shard_scanned = 0
        while it:
            for attempt in range(6):
                try:
                    resp = kin.get_records(ShardIterator=it, Limit=10000)
                    break
                except kin.exceptions.ProvisionedThroughputExceededException:
                    time.sleep(0.5 * (attempt + 1))   # the shard's 5 reads/s are shared with Firehose
            else:
                raise SystemExit("GetRecords kept being throttled; try again in a minute")
            calls += 1
            done = False
            for rec in resp["Records"]:
                arrived = int(rec["ApproximateArrivalTimestamp"].timestamp() * 1000)
                if arrived >= to_ms + 30000:          # 30 s grace: a ping taken just before the
                    done = True                       # window's end may arrive just after it
                    break
                shard_scanned += 1
                ping = json.loads(rec["Data"])
                if ping["truck_id"] == truck and from_ms <= ping["event_ms"] < to_ms:
                    mine.append(ping)
            if done or (resp.get("MillisBehindLatest", 1) == 0 and not resp["Records"]):
                break
            it = resp.get("NextShardIterator")
            time.sleep(0.25)
        scanned += shard_scanned
        print(f"  {sh['ShardId']}: {shard_scanned:,} records read", flush=True)
    mine.sort(key=lambda p: p["event_ms"])
    secs = time.time() - t0
    km = sum(km_between(a, b) for a, b in zip(mine, mine[1:]))
    over = sum(1 for p in mine if p["speed_kmh"] > 80)
    shown = mine if len(mine) <= 6 else mine[:3] + [None] + mine[-3:]
    for p in shown:
        print(f"    ... {len(mine) - 6} more ..." if p is None else
              "    " + json.dumps({k: v for k, v in p.items() if not k.startswith("driver")}))
    result = {"truck": truck, "from": utc(from_ms), "to": utc(to_ms), "records_read": scanned,
              "getrecords_calls": calls, "pings_found": len(mine), "km_driven": round(km, 1),
              "max_kmh": max((p["speed_kmh"] for p in mine), default=None), "pings_over_80": over,
              "seconds": round(secs, 1)}
    print("RESULT replay " + json.dumps(result))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    r = sub.add_parser("replay")
    r.add_argument("--start", required=True, help="UTC, e.g. 2026-10-07T09:00:00Z")
    r.add_argument("--minutes", type=float, default=10)
    r.add_argument("--truck", default="MV-0042")
    a = ap.parse_args()
    settings = conf()
    if a.cmd == "show":
        show(settings)
    else:
        replay(settings, a.start, a.minutes, a.truck)
    return 0


if __name__ == "__main__":
    sys.exit(main())
