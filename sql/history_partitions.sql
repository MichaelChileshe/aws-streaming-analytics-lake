-- fleet_history: pings per day (one partition each). Reads only the dt values and row counts.
SELECT dt, count(*) AS pings, count(DISTINCT truck_id) AS trucks
FROM {db}.fleet_history
GROUP BY dt
ORDER BY dt
