data "aws_caller_identity" "current" {}

# The IAM user (or role) running Terraform: it becomes the Lake Formation administrator.
data "aws_iam_session_context" "current" {
  arn = data.aws_caller_identity.current.arn
}

locals {
  account_id     = data.aws_caller_identity.current.account_id
  lake_bucket    = "mvela-fleet-lake-${local.account_id}-${var.region}"
  results_bucket = "mvela-athena-results-${local.account_id}-${var.region}"
  code_bucket    = "mvela-lake-code-${local.account_id}-${var.region}"
  stream_name    = "mvela-fleet-pings"
  database       = "mvela_fleet"

  raw_prefix     = "raw/json/"
  live_prefix    = "curated/fleet_live/"
  history_prefix = "curated/fleet_history/"

  # Every column of a ping. driver_id and driver_phone are personal information (POPIA).
  ping_columns = [
    { name = "truck_id", type = "string", comment = "MV-0001 .. MV-0300" },
    { name = "depot", type = "string", comment = "PTA, JHB, PLK, BFN" },
    { name = "event_ms", type = "bigint", comment = "ping time, UTC epoch milliseconds" },
    { name = "lat", type = "double", comment = "latitude" },
    { name = "lon", type = "double", comment = "longitude" },
    { name = "speed_kmh", type = "double", comment = "speed, km/h" },
    { name = "heading", type = "int", comment = "degrees" },
    { name = "engine_on", type = "boolean", comment = "ignition" },
    { name = "fuel_pct", type = "double", comment = "tank level, %" },
    { name = "driver_id", type = "string", comment = "PERSONAL INFORMATION" },
    { name = "driver_phone", type = "string", comment = "PERSONAL INFORMATION" },
  ]

  # What operations analysts (and the dashboard) may read: an allow-list, so a column added
  # later stays hidden until someone decides it isn't personal. dt is the partition column.
  analyst_columns = ["truck_id", "depot", "event_ms", "lat", "lon", "speed_kmh", "heading", "engine_on", "fuel_pct", "dt"]
}
