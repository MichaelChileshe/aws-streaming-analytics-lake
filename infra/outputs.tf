output "sim_id" {
  description = "Instance ID of the fleet simulator (for SSM)."
  value       = aws_instance.sim.id
}

output "lake_bucket" {
  description = "The data lake bucket (raw/ and curated/)."
  value       = aws_s3_bucket.lake.bucket
}

output "results_bucket" {
  description = "Athena query results bucket."
  value       = aws_s3_bucket.results.bucket
}

output "stream_name" {
  description = "The fleet's Kinesis data stream."
  value       = aws_kinesis_stream.pings.name
}

output "firehose_name" {
  description = "Firehose stream that writes Parquet into the lake."
  value       = aws_kinesis_firehose_delivery_stream.lake.name
}

output "alerts_function" {
  description = "The speed-alert Lambda function."
  value       = aws_lambda_function.alerts.function_name
}

output "alerts_mapping_uuid" {
  description = "Event source mapping feeding the alert function (changes when alerts_efo changes)."
  value       = aws_lambda_event_source_mapping.alerts.uuid
}

output "alerts_consumer" {
  description = "How the alert function reads the stream."
  value       = var.alerts_efo ? "efo: ${aws_kinesis_stream_consumer.alerts[0].arn}" : "polling (shared throughput)"
}

output "analyst_role_arn" {
  description = "Role an operations analyst assumes."
  value       = aws_iam_role.analyst.arn
}

output "database" {
  description = "Glue database."
  value       = aws_glue_catalog_database.fleet.name
}

output "lake_admins" {
  description = "Lake Formation data lake administrators (set by this configuration)."
  value       = aws_lakeformation_data_lake_settings.this.admins
}

output "app_sha256" {
  description = "SHA-256 of each tool file as uploaded; mvela-sync on the server prints the same."
  value       = { for f in fileset("${path.module}/../app", "*.py") : f => filesha256("${path.module}/../app/${f}") }
}

output "history_location" {
  description = "Where the CTAS migration writes fleet_history (Parquet, partitioned by dt)."
  value       = "s3://${aws_s3_bucket.lake.bucket}/${local.history_prefix}"
}
