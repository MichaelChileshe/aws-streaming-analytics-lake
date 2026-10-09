-- Q1 on Parquet WITHOUT the partition filter: columnar helps (3 of 12 columns), but every day's
-- folder is opened. This is what a dashboard query costs when someone forgets "dt = ...".
SELECT truck_id,
       count(*)                     AS pings,
       max(speed_kmh)               AS max_kmh,
       round(avg(speed_kmh), 1)     AS avg_kmh,
       count_if(speed_kmh > 80) * 5 AS seconds_over_80
FROM {db}.fleet_history
WHERE event_ms >= {day_start_ms} AND event_ms < {day_end_ms}
GROUP BY truck_id
ORDER BY truck_id
