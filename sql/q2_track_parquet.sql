-- Q2, the lake way: the same 15 minutes from fleet_history.
SELECT truck_id, event_ms, lat, lon, speed_kmh, heading
FROM {db}.fleet_history
WHERE dt = '{day}'
  AND truck_id = '{truck}'
  AND event_ms >= {day_start_ms} + 28800000 AND event_ms < {day_start_ms} + 29700000
ORDER BY event_ms
