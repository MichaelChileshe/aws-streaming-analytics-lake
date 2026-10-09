variable "region" {
  description = "Region for everything."
  type        = string
  default     = "us-east-1"
}

variable "az" {
  description = "Availability Zone for the simulator's subnet."
  type        = string
  default     = "us-east-1a"
}

variable "vpc_cidr" {
  description = "CIDR block of the lab VPC."
  type        = string
  default     = "10.130.0.0/16"
}

variable "instance_type" {
  description = "Fleet simulator instance type (it also generates the 7-day history)."
  type        = string
  default     = "c7i.large"
}

variable "shard_count" {
  description = "Shards in the fleet stream. One shard takes 1 MB/s or 1,000 records/s in; the fleet sends 60 records/s."
  type        = number
  default     = 2
}

variable "firehose_buffer_seconds" {
  description = "How long Firehose collects records before it writes a Parquet file (60-900 s)."
  type        = number
  default     = 60

  validation {
    condition     = var.firehose_buffer_seconds >= 60 && var.firehose_buffer_seconds <= 900
    error_message = "firehose_buffer_seconds must be between 60 and 900."
  }
}

variable "speed_limit_kmh" {
  description = "Speed above which a ping raises an alert (heavy vehicles in South Africa: 80 km/h)."
  type        = number
  default     = 80
}

variable "analyst_scan_limit_gb" {
  description = "Most data one analyst query may scan before Athena cancels it."
  type        = number
  default     = 1
}

variable "engineering_scan_limit_gb" {
  description = "Most data one engineering query may scan before Athena cancels it."
  type        = number
  default     = 20
}

variable "lf_cross_account_version" {
  description = "Lake Formation cross-account sharing version the account already uses (from the snapshot taken before the first apply); kept unchanged."
  type        = string
  default     = "4"

  validation {
    condition     = contains(["1", "2", "3", "4"], var.lf_cross_account_version)
    error_message = "lf_cross_account_version must be 1, 2, 3 or 4 (version 5 is one-way; don't set it from here)."
  }
}

# ---- phase switches: set in phases.auto.tfvars as the build goes on ----

variable "alerts_efo" {
  description = "Read the stream for the alert function through an enhanced fan-out consumer (push, dedicated 2 MB/s per shard) instead of shared polling."
  type        = bool
  default     = false
}

variable "history_ready" {
  description = "The CTAS has created fleet_history: grant the analyst role its non-personal columns."
  type        = bool
  default     = false
}

variable "quicksight_principal_arn" {
  description = "Optional: the Amazon Quick Sight user ARN to grant the same non-personal columns of fleet_live (empty = no grant)."
  type        = string
  default     = ""

  validation {
    condition     = var.quicksight_principal_arn == "" || can(regex("^arn:aws:quicksight:", var.quicksight_principal_arn))
    error_message = "quicksight_principal_arn must be a Quick Sight user or group ARN (arn:aws:quicksight:...), or empty."
  }
}
