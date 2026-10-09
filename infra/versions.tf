terraform {
  required_version = ">= 1.11.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.60"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }

  # Remote state in the bucket bootstrap/ created (shared with earlier projects, one key each).
  # The bucket name contains the account ID, so it is passed at init time:
  #   terraform init -backend-config="bucket=nkosi-tfstate-<account id>"
  # use_lockfile = S3-native state locking (no DynamoDB lock table needed).
  backend "s3" {
    key          = "aws-streaming-analytics-lake/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = "aws-streaming-analytics-lake"
      ManagedBy = "terraform"
    }
  }
}
