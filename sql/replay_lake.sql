-- The replay window from the lake, to compare with what the stream replay found.
SELECT count(*) AS pings, min(event_ms) AS first_ms, max(event_ms) AS last_ms, max(speed_kmh) AS max_kmh
FROM {db}.fleet_live
WHERE dt = '{day}'
  AND truck_id = '{truck}'
  AND event_ms >= {from_ms} AND event_ms < {to_ms}
