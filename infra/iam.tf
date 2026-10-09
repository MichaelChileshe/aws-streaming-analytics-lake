# One role per job, each scoped to the resources it touches.

locals {
  glue_catalog_arn = "arn:aws:glue:${var.region}:${local.account_id}:catalog"
  glue_db_arn      = "arn:aws:glue:${var.region}:${local.account_id}:database/${local.database}"
  glue_tables_arn  = "arn:aws:glue:${var.region}:${local.account_id}:table/${local.database}/*"
}

# ---- the fleet simulator: put pings, re-read them (replay), upload the history, read its code ----

resource "aws_iam_role" "sim" {
  name = "mvela-fleet-sim-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "sim" {
  name = "stream-history-code"
  role = aws_iam_role.sim.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteAndReplayTheStream"
        Effect = "Allow"
        Action = ["kinesis:PutRecord", "kinesis:PutRecords", "kinesis:DescribeStreamSummary",
        "kinesis:ListShards", "kinesis:GetShardIterator", "kinesis:GetRecords"]
        Resource = aws_kinesis_stream.pings.arn
      },
      {
        Sid      = "UploadTheLegacyExport"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.lake.arn}/${local.raw_prefix}*"
      },
      {
        Sid      = "ReadTheCode"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.code.arn}/app/*"
      },
      {
        Sid       = "ListTheCode"
        Effect    = "Allow"
        Action    = ["s3:ListBucket"]
        Resource  = aws_s3_bucket.code.arn
        Condition = { StringLike = { "s3:prefix" = ["app/*", "app/"] } }
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sim_ssm" {
  role       = aws_iam_role.sim.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "sim" {
  name = "mvela-fleet-sim-profile"
  role = aws_iam_role.sim.name
}

# ---- Firehose: read the stream, read the table schema, write Parquet into curated/fleet_live/ ----

resource "aws_iam_role" "firehose" {
  name = "mvela-firehose-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "firehose.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "firehose" {
  name = "stream-to-lake"
  role = aws_iam_role.firehose.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadTheStream"
        Effect   = "Allow"
        Action   = ["kinesis:DescribeStream", "kinesis:DescribeStreamSummary", "kinesis:GetShardIterator", "kinesis:GetRecords", "kinesis:ListShards"]
        Resource = aws_kinesis_stream.pings.arn
      },
      {
        Sid      = "ReadTheSchema"
        Effect   = "Allow"
        Action   = ["glue:GetTable", "glue:GetTableVersion", "glue:GetTableVersions"]
        Resource = [local.glue_catalog_arn, local.glue_db_arn, "arn:aws:glue:${var.region}:${local.account_id}:table/${local.database}/fleet_live"]
      },
      {
        Sid      = "TheBucket"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation", "s3:ListBucket", "s3:ListBucketMultipartUploads"]
        Resource = aws_s3_bucket.lake.arn
      },
      {
        Sid      = "WriteLiveAndErrors"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:AbortMultipartUpload"]
        Resource = ["${aws_s3_bucket.lake.arn}/${local.live_prefix}*", "${aws_s3_bucket.lake.arn}/errors/*"]
      },
      {
        Sid      = "DeliveryErrorLogs"
        Effect   = "Allow"
        Action   = ["logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.firehose.arn}:log-stream:*"
      },
    ]
  })
}

# ---- the alert function: read the stream (polling) or its enhanced fan-out consumer ----

resource "aws_iam_role" "alerts" {
  name = "mvela-speed-alerts-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "alerts" {
  name = "read-the-stream"
  role = aws_iam_role.alerts.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "PollTheStream"
        Effect   = "Allow"
        Action   = ["kinesis:DescribeStream", "kinesis:DescribeStreamSummary", "kinesis:GetRecords", "kinesis:GetShardIterator", "kinesis:ListShards"]
        Resource = aws_kinesis_stream.pings.arn
      },
      {
        Sid      = "EnhancedFanOut"
        Effect   = "Allow"
        Action   = ["kinesis:SubscribeToShard", "kinesis:DescribeStreamConsumer"]
        Resource = [aws_kinesis_stream.pings.arn, "${aws_kinesis_stream.pings.arn}/consumer/*"]
      },
      {
        Sid      = "ListStreamsIsAccountWide"
        Effect   = "Allow"
        Action   = "kinesis:ListStreams"
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "alerts_logs" {
  role       = aws_iam_role.alerts.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ---- the operations analyst: Athena in mvela-analysts, catalog reads, Lake Formation data access.
# No S3 permission on the lake at all: every byte it reads comes through Lake Formation. ----

resource "aws_iam_role" "analyst" {
  name                 = "mvela-ops-analyst"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${local.account_id}:root" }
      Action    = "sts:AssumeRole"
      Condition = { ArnEquals = { "aws:PrincipalArn" = data.aws_iam_session_context.current.issuer_arn } }
    }]
  })
}

resource "aws_iam_role_policy" "analyst" {
  name = "athena-analysts-workgroup"
  role = aws_iam_role.analyst.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AnalystsWorkgroupOnly"
        Effect = "Allow"
        Action = ["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults",
        "athena:StopQueryExecution", "athena:GetWorkGroup", "athena:ListQueryExecutions", "athena:BatchGetQueryExecution"]
        Resource = aws_athena_workgroup.analysts.arn
      },
      {
        Sid    = "CatalogReads"
        Effect = "Allow"
        Action = ["glue:GetDatabase", "glue:GetDatabases", "glue:GetTable", "glue:GetTables",
        "glue:GetPartition", "glue:GetPartitions", "glue:BatchGetPartition"]
        Resource = [local.glue_catalog_arn, local.glue_db_arn, local.glue_tables_arn,
        "arn:aws:glue:${var.region}:${local.account_id}:database/default"]
      },
      {
        Sid      = "LakeFormationVendsTheData"
        Effect   = "Allow"
        Action   = ["lakeformation:GetDataAccess"]
        Resource = "*"
      },
      {
        Sid      = "OwnQueryResults"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"]
        Resource = "${aws_s3_bucket.results.arn}/analysts/*"
      },
      {
        Sid       = "ListOwnResultsOnly"
        Effect    = "Allow"
        Action    = ["s3:ListBucket"]
        Resource  = aws_s3_bucket.results.arn
        Condition = { StringLike = { "s3:prefix" = ["analysts/", "analysts/*"] } }
      },
      {
        Sid      = "ResultsBucketLocation"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation"]
        Resource = aws_s3_bucket.results.arn
      },
    ]
  })
}
