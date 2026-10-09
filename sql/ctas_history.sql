-- The one-time migration: read the JSON export once, write it back as Parquet (Snappy),
-- one folder per UTC day. CTAS registers the table and its 7 partitions in the Glue catalog.
-- The partition column (dt) must be the LAST column of the SELECT.
CREATE TABLE {db}.fleet_history
WITH (
  format            = 'PARQUET',
  write_compression = 'SNAPPY',
  external_location = '{history_location}',
  partitioned_by    = ARRAY['dt']
) AS
SELECT truck_id, depot, event_ms, lat, lon, speed_kmh, heading, engine_on, fuel_pct,
       driver_id, driver_phone,
       date_format(from_unixtime(event_ms / 1000), '%Y-%m-%d') AS dt
FROM {db}.raw_pings_json
