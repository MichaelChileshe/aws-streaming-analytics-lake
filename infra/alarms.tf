# Two alarms on the two promises this pipeline makes. No actions wired here (state only, visible
# in the console); in production they'd notify the on-call channel through SNS.

# Promise 1: the lake is never more than 5 minutes behind the trucks.
resource "aws_cloudwatch_metric_alarm" "lake_freshness" {
  alarm_name          = "mvela-lake-freshness"
  alarm_description   = "Oldest record waiting in Firehose is older than 5 minutes: dashboards are going stale."
  namespace           = "AWS/Firehose"
  metric_name         = "DeliveryToS3.DataFreshness"
  dimensions          = { DeliveryStreamName = aws_kinesis_firehose_delivery_stream.lake.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  threshold           = 300
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

# Promise 2: speeding alerts keep up with the stream (records wait no more than a minute).
resource "aws_cloudwatch_metric_alarm" "alerts_iterator_age" {
  alarm_name          = "mvela-alerts-iterator-age"
  alarm_description   = "The speed-alert function is more than 60 s behind the stream: alerts are late."
  namespace           = "AWS/Lambda"
  metric_name         = "IteratorAge"
  dimensions          = { FunctionName = aws_lambda_function.alerts.function_name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  threshold           = 60000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}
