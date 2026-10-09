# The fleet stream and its two readers:
#   Firehose   -> Parquet files in the lake (firehose.tf), minutes behind
#   Lambda     -> speeding alerts, seconds behind
# Provisioned mode: 2 shards = 2 MB/s or 2,000 records/s in, 4 MB/s out, for US$0.03 an hour.
# Records are encrypted at rest with the AWS managed key aws/kinesis (no key to manage).

resource "aws_kinesis_stream" "pings" {
  name             = local.stream_name
  shard_count      = var.shard_count
  retention_period = 24

  stream_mode_details {
    stream_mode = "PROVISIONED"
  }

  encryption_type = "KMS"
  kms_key_id      = "alias/aws/kinesis"

  # Per-shard record counts (billed like 2 custom metrics): shows how the truck_id key spreads the load.
  shard_level_metrics = ["IncomingRecords"]

  # Deregister consumers on destroy, so the stream can always be deleted.
  enforce_consumer_deletion = true
}

# Enhanced fan-out: a dedicated 2 MB/s per shard pipe that PUSHES records to this one consumer
# (SubscribeToShard over HTTP/2), instead of sharing the shard's 5 reads/s with everyone else.
resource "aws_kinesis_stream_consumer" "alerts" {
  count      = var.alerts_efo ? 1 : 0
  name       = "mvela-speed-alerts-efo"
  stream_arn = aws_kinesis_stream.pings.arn
}

data "archive_file" "alerts" {
  type        = "zip"
  source_file = "${path.module}/../lambda/alerts.py"
  output_path = "${path.module}/../build/alerts.zip"
}

resource "aws_cloudwatch_log_group" "alerts" {
  name              = "/aws/lambda/mvela-speed-alerts"
  retention_in_days = 7
}

resource "aws_lambda_function" "alerts" {
  function_name    = "mvela-speed-alerts"
  role             = aws_iam_role.alerts.arn
  runtime          = "python3.13"
  architectures    = ["arm64"]
  handler          = "alerts.handler"
  filename         = data.archive_file.alerts.output_path
  source_code_hash = data.archive_file.alerts.output_base64sha256
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      SPEED_LIMIT_KMH = tostring(var.speed_limit_kmh)
      CONSUMER_MODE   = var.alerts_efo ? "efo" : "polling"
    }
  }

  # The log group first (so Lambda doesn't create an unmanaged one) and the permissions first.
  depends_on = [aws_cloudwatch_log_group.alerts, aws_iam_role_policy.alerts, aws_iam_role_policy_attachment.alerts_logs]
}

# Polling (shared throughput) reads the stream itself; enhanced fan-out reads the consumer.
# Changing alerts_efo replaces this mapping. LATEST: alerts are about now, not about the backlog.
resource "aws_lambda_event_source_mapping" "alerts" {
  function_name     = aws_lambda_function.alerts.arn
  event_source_arn  = var.alerts_efo ? aws_kinesis_stream_consumer.alerts[0].arn : aws_kinesis_stream.pings.arn
  starting_position = "LATEST"
  batch_size        = 500

  depends_on = [aws_iam_role_policy.alerts]
}
