# The Glue Data Catalog: one database, two tables declared here, one created by a query later.
#   raw_pings_json  the legacy export as it lands: JSON, unpartitioned, uncompressed
#   fleet_live      what Firehose writes: Parquet, one folder per UTC day (dt=YYYY-MM-DD)
#   fleet_history   (created by the CTAS migration, not by Terraform) the 7 days of JSON
#                   rewritten once as Parquet, partitioned by dt
# The database waits for the Lake Formation settings: created after them, it has no
# IAMAllowedPrincipals grant, so Lake Formation (not IAM alone) decides who reads what.

resource "aws_glue_catalog_database" "fleet" {
  name        = local.database
  description = "Mvelaphanda fleet telemetry lake"

  depends_on = [aws_lakeformation_data_lake_settings.this]
}

resource "aws_glue_catalog_table" "raw_json" {
  name          = "raw_pings_json"
  database_name = aws_glue_catalog_database.fleet.name
  description   = "Legacy hourly JSON export, one flat prefix: every query reads every file"
  table_type    = "EXTERNAL_TABLE"
  parameters = {
    classification = "json"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lake.bucket}/${local.raw_prefix}"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      name                  = "openx-json"
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
    }

    dynamic "columns" {
      for_each = local.ping_columns
      content {
        name    = columns.value.name
        type    = columns.value.type
        comment = columns.value.comment
      }
    }
  }
}

# Partition projection: Athena works out the dt folders from these rules instead of looking
# them up, so a new day's folder from Firehose is queryable at once (no crawler, no MSCK REPAIR).
resource "aws_glue_catalog_table" "fleet_live" {
  name          = "fleet_live"
  database_name = aws_glue_catalog_database.fleet.name
  description   = "Live pings delivered by Firehose as Parquet, partitioned by UTC day"
  table_type    = "EXTERNAL_TABLE"
  parameters = {
    classification                = "parquet"
    "projection.enabled"          = "true"
    "projection.dt.type"          = "date"
    "projection.dt.format"        = "yyyy-MM-dd"
    "projection.dt.range"         = "NOW-30DAYS,NOW"
    "projection.dt.interval"      = "1"
    "projection.dt.interval.unit" = "DAYS"
    "storage.location.template"   = "s3://${aws_s3_bucket.lake.bucket}/${local.live_prefix}dt=$${dt}/"
  }

  partition_keys {
    name    = "dt"
    type    = "string"
    comment = "UTC day the ping arrived, YYYY-MM-DD"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lake.bucket}/${local.live_prefix}"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      name                  = "parquet"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    dynamic "columns" {
      for_each = local.ping_columns
      content {
        name    = columns.value.name
        type    = columns.value.type
        comment = columns.value.comment
      }
    }
  }
}
