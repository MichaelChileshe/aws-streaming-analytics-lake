# Firehose: reads the stream, converts each JSON ping to a Parquet row using fleet_live's schema
# from the Glue catalog, and writes one Parquet file per buffer (every 60 s by default) into
#   curated/fleet_live/dt=<UTC day of arrival>/
# Format conversion needs a buffer of at least 64 MB; at ~12 KB/s the 60 s timer always wins.

resource "aws_cloudwatch_log_group" "firehose" {
  name              = "/aws/kinesisfirehose/mvela-fleet-to-lake"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_stream" "firehose_s3" {
  name           = "DestinationDelivery"
  log_group_name = aws_cloudwatch_log_group.firehose.name
}

resource "aws_kinesis_firehose_delivery_stream" "lake" {
  name        = "mvela-fleet-to-lake"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.pings.arn
    role_arn           = aws_iam_role.firehose.arn
  }

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = aws_s3_bucket.lake.arn
    prefix              = "${local.live_prefix}dt=!{timestamp:yyyy-MM-dd}/"
    error_output_prefix = "errors/fleet_live/!{firehose:error-output-type}/dt=!{timestamp:yyyy-MM-dd}/"
    buffering_size      = 64
    buffering_interval  = var.firehose_buffer_seconds
    custom_time_zone    = "UTC"

    data_format_conversion_configuration {
      input_format_configuration {
        deserializer {
          open_x_json_ser_de {}
        }
      }

      output_format_configuration {
        serializer {
          parquet_ser_de {
            compression = "SNAPPY"
          }
        }
      }

      schema_configuration {
        database_name = aws_glue_catalog_database.fleet.name
        table_name    = aws_glue_catalog_table.fleet_live.name
        role_arn      = aws_iam_role.firehose.arn
        region        = var.region
      }
    }

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose.name
      log_stream_name = aws_cloudwatch_log_stream.firehose_s3.name
    }
  }

  # The role's permissions (IAM and Lake Formation) exist before Firehose first uses them.
  depends_on = [aws_iam_role_policy.firehose, aws_lakeformation_permissions.firehose_live]
}
