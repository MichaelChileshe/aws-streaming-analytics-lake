-- Q1, the old way: one day's driving summary per truck, from the raw hourly JSON export.
-- The WHERE clause keeps one day of rows, but the files aren't partitioned and JSON isn't
-- columnar: Athena reads every byte of every file to find them.
SELECT truck_id,
       count(*)                     AS pings,
       max(speed_kmh)               AS max_kmh,
       round(avg(speed_kmh), 1)     AS avg_kmh,
       count_if(speed_kmh > 80) * 5 AS seconds_over_80
FROM {db}.raw_pings_json
WHERE event_ms >= {day_start_ms} AND event_ms < {day_end_ms}
GROUP BY truck_id
ORDER BY truck_id
