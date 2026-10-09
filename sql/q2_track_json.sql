-- Q2, the old way: "where was this truck between 10:00 and 10:15 (SAST) that day?"
-- 180 pings out of 36 million, and Athena still reads the whole export.
SELECT truck_id, event_ms, lat, lon, speed_kmh, heading
FROM {db}.raw_pings_json
WHERE truck_id = '{truck}'
  AND event_ms >= {day_start_ms} + 28800000 AND event_ms < {day_start_ms} + 29700000
ORDER BY event_ms
