data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_instance" "sim" {
  ami                         = data.aws_ssm_parameter.al2023.insecure_value
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.public_a.id
  vpc_security_group_ids      = [aws_security_group.sim.id]
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.sim.name

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  root_block_device {
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/templates/userdata.sh.tftpl", {
    region      = var.region
    stream      = aws_kinesis_stream.pings.name
    lake_bucket = aws_s3_bucket.lake.bucket
    raw_prefix  = local.raw_prefix
    code_bucket = aws_s3_bucket.code.bucket
  })
  user_data_replace_on_change = true

  tags = { Name = "mvela-fleet-sim" }

  # The boot script needs its code in S3, a route to the internet and an outbound rule before it runs.
  depends_on = [aws_s3_object.app, aws_route.internet, aws_route_table_association.public_a, aws_vpc_security_group_egress_rule.sim_all, aws_iam_role_policy.sim]

  lifecycle {
    ignore_changes = [ami] # a newer AMI later shouldn't replace the server mid-build
  }
}
