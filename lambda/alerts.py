"""mvela-speed-alerts: reads the fleet stream and raises a speeding alert within seconds of the ping.

For every batch it also measures how long each ping took to get here (now - event_ms) and
publishes that as a CloudWatch metric through the embedded metric format (EMF: structured log
lines that CloudWatch turns into metrics, no PutMetricData calls). Dimension Consumer = how the
function reads the stream (polling = shared throughput, efo = enhanced fan-out), so the two
modes can be compared on one graph.

Alerts carry the truck, never the driver: driver_id and driver_phone stay out of the logs
(the control room looks the driver up from the truck in the HR system).
"""
import base64
import json
import os
import time

LIMIT = float(os.environ.get("SPEED_LIMIT_KMH", "80"))
MODE = os.environ.get("CONSUMER_MODE", "polling")
NAMESPACE = "Mvelaphanda/Fleet"
REPEAT_MS = 5 * 60 * 1000          # one alert per truck per 5 minutes (per warm function instance)
_last_alert = {}


def _emf(metrics, values):
    """One EMF log line. values: {metric name: number or list of up to 100 numbers}."""
    doc = {
        "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
            "Namespace": NAMESPACE, "Dimensions": [["Consumer"]],
            "Metrics": [{"Name": n, "Unit": u} for n, u in metrics]}]},
        "Consumer": MODE,
    }
    doc.update(values)
    print(json.dumps(doc))


def handler(event, context):
    now = int(time.time() * 1000)
    latencies, speeding, alerts, bad = [], 0, 0, 0
    for rec in event.get("Records", []):
        try:
            ping = json.loads(base64.b64decode(rec["kinesis"]["data"]))
        except (ValueError, KeyError):
            bad += 1
            continue
        latencies.append(now - int(ping["event_ms"]))
        if float(ping["speed_kmh"]) <= LIMIT:
            continue
        speeding += 1
        last = _last_alert.get(ping["truck_id"], 0)
        if ping["event_ms"] - last < REPEAT_MS:
            continue
        _last_alert[ping["truck_id"]] = ping["event_ms"]
        alerts += 1
        print(json.dumps({"alert": "SPEEDING", "truck_id": ping["truck_id"], "depot": ping["depot"],
                          "speed_kmh": ping["speed_kmh"], "limit_kmh": LIMIT, "lat": ping["lat"],
                          "lon": ping["lon"], "event_ms": ping["event_ms"],
                          "ms_after_ping": now - int(ping["event_ms"])}))
    for i in range(0, len(latencies), 100):            # EMF takes up to 100 values per metric per line
        _emf([("PingToAlertLatency", "Milliseconds")], {"PingToAlertLatency": latencies[i:i + 100]})
    _emf([("PingsRead", "Count"), ("SpeedingPings", "Count"), ("AlertsRaised", "Count"), ("BadRecords", "Count")],
         {"PingsRead": len(latencies), "SpeedingPings": speeding, "AlertsRaised": alerts, "BadRecords": bad})
    s = sorted(latencies)
    print(json.dumps({"batch": len(event.get("Records", [])), "consumer": MODE,
                      "p50_ms": s[len(s) // 2] if s else None, "max_ms": s[-1] if s else None,
                      "speeding": speeding, "alerts": alerts, "bad": bad}))
    return {"pings": len(latencies), "alerts": alerts}
