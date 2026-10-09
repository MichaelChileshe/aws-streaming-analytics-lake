# Three Athena workgroups = separate query histories, result folders and cost guardrails.
# enforce_workgroup_configuration: a query can't send its results somewhere else or skip encryption.
# bytes_scanned_cutoff_per_query: Athena cancels a query that would scan more (it is billed for
# what it scanned up to that point).

resource "aws_athena_workgroup" "engineering" {
  name          = "mvela-engineering"
  description   = "Data engineering: the raw export, the migration, the lake"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.engineering_scan_limit_gb * 1024 * 1024 * 1024

    engine_version {
      selected_engine_version = "AUTO"
    }

    result_configuration {
      output_location = "s3://${aws_s3_bucket.results.bucket}/engineering/"
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}

resource "aws_athena_workgroup" "analysts" {
  name          = "mvela-analysts"
  description   = "Operations analysts and the dashboard: non-personal columns, small queries"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.analyst_scan_limit_gb * 1024 * 1024 * 1024

    engine_version {
      selected_engine_version = "AUTO"
    }

    result_configuration {
      output_location = "s3://${aws_s3_bucket.results.bucket}/analysts/"
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}

# One-off migrations. A CTAS chooses where its table's files go (external_location); a workgroup
# that enforces its own settings rejects that, so the migration runs here. Only engineering
# (me) can use it; its own query results still go to their own folder.
resource "aws_athena_workgroup" "migration" {
  name          = "mvela-migration"
  description   = "One-off CTAS migrations that write table data to the lake (external_location)"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = false
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.engineering_scan_limit_gb * 1024 * 1024 * 1024

    engine_version {
      selected_engine_version = "AUTO"
    }

    result_configuration {
      output_location = "s3://${aws_s3_bucket.results.bucket}/migration/"
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}
