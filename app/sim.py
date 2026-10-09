"""fleet-sim: the live fleet. Every truck pings every 5 seconds into the Kinesis data stream.

  fleet-sim                 # run until stopped (it runs as a systemd unit: systemctl stop fleet-sim)
  fleet-sim --minutes 2     # run 2 minutes, print totals, exit

Trucks ping at different moments (each has its own offset inside the 5 seconds), so the stream
gets an even 60 records per second rather than 300 at once. event_ms is stamped the moment
a ping is built, just before PutRecords: every latency measured downstream starts there.
Partition key = truck_id: one truck's pings stay in order on one shard.
"""
import argparse
import json
import signal
import sys
import time

from common import client, conf, now_ms, pct
from fleet import PING_SECONDS, make_fleet

STOP = False


def _stop(*_):
    global STOP
    STOP = True


def put_batch(kin, stream, records, stats):
    """PutRecords with one retry for records the stream refused (throttling or internal errors)."""
    t0 = time.time()
    resp = kin.put_records(StreamName=stream, Records=records)
    stats["put_ms"].append((time.time() - t0) * 1000)
    if resp.get("FailedRecordCount", 0):
        retry = []
        for rec, res in zip(records, resp["Records"]):
            if "ErrorCode" in res:
                stats["refused"] += 1
                if res["ErrorCode"] == "ProvisionedThroughputExceededException":
                    stats["throttled"] += 1
                retry.append(rec)
        time.sleep(0.2)
        resp2 = kin.put_records(StreamName=stream, Records=retry)
        stats["lost"] += resp2.get("FailedRecordCount", 0)
    stats["sent"] += len(records)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=float, default=0, help="0 = until stopped")
    a = ap.parse_args()
    settings = conf()
    kin = client("kinesis", settings["REGION"])
    stream = settings["STREAM"]
    fleet = make_fleet(salt=int(time.time()) // 86400)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    stats = {"sent": 0, "refused": 0, "throttled": 0, "lost": 0, "put_ms": []}
    t_start = time.time()
    t_end = t_start + a.minutes * 60 if a.minutes else None
    print(f"fleet-sim: {len(fleet)} trucks, one ping each every {PING_SECONDS} s -> {stream} "
          f"({'until stopped' if not t_end else f'{a.minutes:g} min'})", flush=True)
    next_tick = int(t_start) + 1
    last_report = t_start
    while not STOP and (t_end is None or time.time() < t_end):
        time.sleep(max(0.0, next_tick - time.time()))
        slot = next_tick % PING_SECONDS
        records = []
        for i, truck in enumerate(fleet):
            if i % PING_SECONDS != slot:
                continue
            truck.step(True)          # live: the whole fleet is on shift
            records.append({"Data": truck.json(now_ms(), True).encode(),
                            "PartitionKey": truck.truck_id})
        try:
            put_batch(kin, stream, records, stats)
        except Exception as e:                       # keep the fleet running through a blip
            stats["lost"] += len(records)
            stats["errors"] = stats.get("errors", 0) + 1
            print(f"  PutRecords failed ({type(e).__name__}: {e}); {len(records)} pings lost, carrying on", flush=True)
        next_tick += 1
        if time.time() - last_report >= 30:
            last_report = time.time()
            mins = (last_report - t_start) / 60
            print(f"  {mins:5.1f} min  sent {stats['sent']:,}  refused {stats['refused']}  "
                  f"throttled {stats['throttled']}  lost {stats['lost']}  "
                  f"PutRecords p50 {pct(stats['put_ms'][-60:], 50) or 0:.0f} ms", flush=True)
    secs = time.time() - t_start
    puts = stats["put_ms"]
    print("RESULT " + json.dumps({
        "seconds": round(secs), "sent": stats["sent"], "per_second": round(stats["sent"] / secs, 1),
        "refused_then_retried": stats["refused"], "throttled": stats["throttled"], "lost": stats["lost"],
        "failed_calls": stats.get("errors", 0),
        "putrecords_calls": len(puts), "putrecords_p50_ms": round(pct(puts, 50) or 0, 1),
        "putrecords_p99_ms": round(pct(puts, 99) or 0, 1)}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
