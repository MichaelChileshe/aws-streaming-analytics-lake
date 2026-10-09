# One public subnet for the fleet simulator, and a gateway endpoint so its S3 traffic (the
# 7.7 GB history upload, its code) stays on the AWS network for free. The public IP is for
# outbound only (packages, Kinesis, SSM): the security group has no inbound rules.

resource "aws_vpc" "lab" {
  cidr_block = var.vpc_cidr
  tags       = { Name = "mvela-lake-vpc" }
}

resource "aws_subnet" "public_a" {
  vpc_id            = aws_vpc.lab.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 1)
  availability_zone = var.az
  tags              = { Name = "mvela-lake-public-a" }
}

resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id
  tags   = { Name = "mvela-lake-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.lab.id
  tags   = { Name = "mvela-lake-public-rt" }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.lab.id
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.lab.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id]
  tags              = { Name = "mvela-lake-s3-endpoint" }
}

resource "aws_security_group" "sim" {
  name        = "mvela-fleet-sim-sg"
  description = "Fleet simulator - no inbound, SSM only"
  vpc_id      = aws_vpc.lab.id
  tags        = { Name = "mvela-fleet-sim-sg" }
}

# Terraform removes the default allow-all egress rule from groups it creates, so outbound is explicit.
resource "aws_vpc_security_group_egress_rule" "sim_all" {
  security_group_id = aws_security_group.sim.id
  description       = "Outbound: packages, SSM, Kinesis, S3"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}
