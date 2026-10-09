-- The control-room view: the last 15 minutes per depot (non-personal columns only).
SELECT depot,
       count(DISTINCT truck_id)     AS trucks,
       count(*)                     AS pings,
       round(avg(speed_kmh), 1)     AS avg_kmh,
       max(speed_kmh)               AS max_kmh,
       count_if(speed_kmh > 80)     AS pings_over_80
FROM {db}.fleet_live
WHERE dt = '{day}'
  AND event_ms >= {since_ms}
GROUP BY depot
ORDER BY depot
