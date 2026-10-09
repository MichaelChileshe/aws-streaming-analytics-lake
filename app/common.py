"""Settings and small helpers shared by the tools on mvela-fleet-sim (aws-streaming-analytics-lake).

The boot script writes /etc/mvela-lake.conf (KEY=value lines) from Terraform's values, so the
tools never hard-code a bucket or stream name.
"""
import datetime as dt
import math
import os
import time

CONF = "/etc/mvela-lake.conf"


def conf():
    """KEY=value lines from /etc/mvela-lake.conf; environment variables win (handy for testing)."""
    out = {}
    if os.path.exists(CONF):
        for line in open(CONF):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    for k in ("REGION", "STREAM", "LAKE_BUCKET", "RAW_PREFIX"):
        if os.environ.get(k):
            out[k] = os.environ[k]
    missing = [k for k in ("REGION", "STREAM", "LAKE_BUCKET", "RAW_PREFIX") if not out.get(k)]
    if missing:
        raise SystemExit(f"missing settings {missing}: is {CONF} there? (written by the boot script)")
    return out


def client(name, region):
    import boto3
    from botocore.config import Config
    return boto3.client(name, region_name=region,
                        config=Config(retries={"max_attempts": 3, "mode": "standard"},
                                      max_pool_connections=32))


def now_ms():
    return int(time.time() * 1000)


def utc(ms):
    """Epoch milliseconds -> '2026-10-07 09:15:02.123 UTC'."""
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"


def parse_utc(text):
    """'2026-10-07T09:15:00Z' (or without Z, or with a space) -> aware UTC datetime."""
    t = text.strip().replace(" ", "T").rstrip("Z")
    return dt.datetime.fromisoformat(t).replace(tzinfo=dt.timezone.utc)


def pct(values, p):
    """Percentile (nearest rank) of a list of numbers; None for an empty list."""
    if not values:
        return None
    s = sorted(values)
    k = max(0, min(len(s) - 1, math.ceil(p / 100.0 * len(s)) - 1))
    return s[k]
