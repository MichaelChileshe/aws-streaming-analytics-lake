-- Q1, the lake way: the same question on fleet_history (Parquet, partitioned by dt).
-- dt = '{day}' prunes to one day's folder; Parquet lets Athena read only the 3 columns used.
SELECT truck_id,
       count(*)                     AS pings,
       max(speed_kmh)               AS max_kmh,
       round(avg(speed_kmh), 1)     AS avg_kmh,
       count_if(speed_kmh > 80) * 5 AS seconds_over_80
FROM {db}.fleet_history
WHERE dt = '{day}'
  AND event_ms >= {day_start_ms} AND event_ms < {day_end_ms}
GROUP BY truck_id
ORDER BY truck_id
