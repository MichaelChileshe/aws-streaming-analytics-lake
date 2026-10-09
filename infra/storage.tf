# Three buckets:
#   lake     raw/json/ (the legacy hourly export, unpartitioned)  and  curated/ (Parquet, partitioned)
#   results  Athena query results, one prefix per workgroup, deleted after 7 days
#   code     the simulator's Python tools, copied to the server at boot
# force_destroy: this is a lab, "terraform destroy" empties and removes them.

resource "aws_s3_bucket" "lake" {
  bucket        = local.lake_bucket
  force_destroy = true
}

resource "aws_s3_bucket" "results" {
  bucket        = local.results_bucket
  force_destroy = true
}

resource "aws_s3_bucket" "code" {
  bucket        = local.code_bucket
  force_destroy = true
}

locals {
  buckets = {
    lake    = aws_s3_bucket.lake
    results = aws_s3_bucket.results
    code    = aws_s3_bucket.code
  }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = local.buckets
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = local.buckets
  bucket   = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Refuse any request that isn't over TLS. Every client used here (CLI, SDK, Athena, Firehose,
# Lake Formation) uses TLS, so this can't lock anyone out.
resource "aws_s3_bucket_policy" "tls_only" {
  for_each = local.buckets
  bucket   = each.value.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "TLSOnly"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [each.value.arn, "${each.value.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.all]
}

resource "aws_s3_bucket_lifecycle_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# Query results can contain personal data (an engineer's SELECT *): keep them a week, no longer.
resource "aws_s3_bucket_lifecycle_configuration" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    id     = "expire-results-after-7-days"
    status = "Enabled"
    filter {}
    expiration {
      days = 7
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# The tool code travels through S3: Terraform uploads app/*.py, the server copies them at boot
# (and again whenever mvela-sync runs). etag = the file's MD5, so an edited file is re-uploaded.
resource "aws_s3_object" "app" {
  for_each = fileset("${path.module}/../app", "*.py")
  bucket   = aws_s3_bucket.code.id
  key      = "app/${each.value}"
  source   = "${path.module}/../app/${each.value}"
  etag     = filemd5("${path.module}/../app/${each.value}")
}
