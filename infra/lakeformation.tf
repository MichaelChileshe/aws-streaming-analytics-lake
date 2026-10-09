# Lake Formation: who may read which COLUMNS, enforced for every engine that asks Lake Formation
# for data access (Athena here, Quick Sight through Athena).
#
# ACCOUNT-WIDE SETTING, READ THIS: aws_lakeformation_data_lake_settings replaces the whole
# Data Catalog settings object. It makes me (the identity running Terraform) the data lake
# administrator, and because create_database_default_permissions / create_table_default_permissions
# are left out, they are CLEARED: new databases no longer get the IAMAllowedPrincipals grant
# ("use only IAM access control"). That is what makes this project's database Lake Formation-
# controlled. The cross-account sharing version is set explicitly to what the account already
# uses, so the build never changes it.
#
# Destroying this resource would NOT restore the account: the provider's delete clears the
# admins and defaults and forces CROSS_ACCOUNT_VERSION to "1" (a downgrade AWS doesn't document).
# So the teardown takes it out of Terraform's state first (terraform state rm), destroys
# everything else, and then puts back the snapshot taken before the build (scripts/lf_settings.py).
resource "aws_lakeformation_data_lake_settings" "this" {
  admins = [data.aws_iam_session_context.current.issuer_arn]

  # Both keys, exactly as the API returns them, so later plans show no difference.
  parameters = {
    CROSS_ACCOUNT_VERSION = var.lf_cross_account_version
    SET_CONTEXT           = "TRUE"
  }
}

# The role Lake Formation uses to read the registered location when it hands an engine
# temporary credentials (credential vending). Analysts get NO S3 permissions at all.
resource "aws_iam_role" "lf_registration" {
  name = "mvela-lf-registration-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lakeformation.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "lf_registration" {
  name = "read-write-curated"
  role = aws_iam_role.lf_registration.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "CuratedObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.lake.arn}/curated/*"
      },
      {
        Sid       = "ListCurated"
        Effect    = "Allow"
        Action    = ["s3:ListBucket"]
        Resource  = aws_s3_bucket.lake.arn
        Condition = { StringLike = { "s3:prefix" = ["curated/*", "curated/"] } }
      },
      {
        Sid      = "BucketLocation"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation"]
        Resource = aws_s3_bucket.lake.arn
      },
    ]
  })
}

# Register curated/ (fleet_live + fleet_history). raw/ stays unregistered: only engineering
# reads it, with ordinary IAM S3 permissions.
resource "aws_lakeformation_resource" "curated" {
  arn                     = "${aws_s3_bucket.lake.arn}/curated"
  role_arn                = aws_iam_role.lf_registration.arn
  use_service_linked_role = false

  depends_on = [aws_iam_role_policy.lf_registration, aws_lakeformation_data_lake_settings.this]
}

# Firehose reads fleet_live's schema (glue:GetTable*) to convert JSON to Parquet. On a Lake
# Formation-controlled table that metadata read needs a Lake Formation grant as well as IAM.
resource "aws_lakeformation_permissions" "firehose_live" {
  principal   = aws_iam_role.firehose.arn
  permissions = ["DESCRIBE", "SELECT"]

  table {
    database_name = aws_glue_catalog_database.fleet.name
    name          = aws_glue_catalog_table.fleet_live.name
  }
}

# Operations analysts: the non-personal columns only.
resource "aws_lakeformation_permissions" "analyst_live" {
  principal   = aws_iam_role.analyst.arn
  permissions = ["SELECT"]

  table_with_columns {
    database_name = aws_glue_catalog_database.fleet.name
    name          = aws_glue_catalog_table.fleet_live.name
    column_names  = local.analyst_columns
  }
}

# fleet_history exists only after the CTAS migration; history_ready = true adds this grant.
resource "aws_lakeformation_permissions" "analyst_history" {
  count       = var.history_ready ? 1 : 0
  principal   = aws_iam_role.analyst.arn
  permissions = ["SELECT"]

  table_with_columns {
    database_name = aws_glue_catalog_database.fleet.name
    name          = "fleet_history"
    column_names  = local.analyst_columns
  }
}

# Optional dashboard: the Quick Sight user gets exactly what an analyst gets.
resource "aws_lakeformation_permissions" "quicksight_live" {
  count       = var.quicksight_principal_arn == "" ? 0 : 1
  principal   = var.quicksight_principal_arn
  permissions = ["SELECT"]

  table_with_columns {
    database_name = aws_glue_catalog_database.fleet.name
    name          = aws_glue_catalog_table.fleet_live.name
    column_names  = local.analyst_columns
  }
}
