# 0007 · Terraform with the shared S3-locked state bucket and phases as variables

**Status:** accepted · 2026-10-09

## Context
Built entirely with Terraform, like `aws-dynamodb-data-modeling` before it, instead of the long, mostly repetitive AWS CLI command chains of earlier projects. The state bucket from that project already exists for exactly this.

## Decision
- **Terraform for every resource**; the CLI only for the experiments and the one account-wide step in the teardown.
- **Remote state** in the shared bucket, key `aws-streaming-analytics-lake/terraform.tfstate`, **`use_lockfile = true`** (S3-native locking).
- **Phases as variables** in `infra/phases.auto.tfvars`: `history_ready` (a grant on a table the CTAS creates), `alerts_efo`, `quicksight_principal_arn`.
- **Quality gates** before apply: fmt, validate, tflint, checkov (soft-fail, findings triaged in [`../terraform.md`](../terraform.md)).
- **Default tags** `Project` and `ManagedBy` on everything.
- **Provider versions pinned** by the committed lock file (aws 6.68.0, archive 2.8.1).

## Consequences
- Measured: 60 + 1 + 1 resources across three applies, enhanced fan-out `2 / 1 / 1`, the dashboard grant added and removed, `Destroy complete! Resources: 62 destroyed.`, clean check empty for this project.
- A table created by a query (the CTAS) isn't in the state; Terraform grants on it by name once it exists and removes it with the database.
- Account-wide resources don't fit a project's lifecycle ([0006](0006-snapshot-and-restore-the-account-wide-lake-formation-settings.md)).
- Next: a project-agnostic teardown tool built on the `Project` tag rather than name prefixes, as a separate repo.
