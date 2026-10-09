# The Terraform

## Why

Apart from `aws-terraform-iac-pipeline`, I built my earlier environments from the AWS CLI, chaining commands into long sequences. Most of those chains were the same work every time, and every manual teardown risked one forgotten delete left billing. Since `aws-dynamodb-data-modeling` the infrastructure is code: `apply` builds it, the plan shows exactly what will change, `destroy` removes it. What I still run by hand are the experiments: the backfill, the queries, the replay, the access checks.

## Layout

| Path | What |
|---|---|
| `bootstrap/main.tf` | The shared state bucket `nkosi-tfstate-<account>`: versioned, AES-256, public access blocked, TLS-only, old versions expire after 90 days, `prevent_destroy`. Created in `aws-dynamodb-data-modeling` and reused; this project only checks it exists. |
| `infra/versions.tf` | Terraform >= 1.11, AWS provider `~> 6.60` (6.68.0 used), archive `~> 2.7` (2.8.1 used), the S3 backend with key `aws-streaming-analytics-lake/terraform.tfstate` and **`use_lockfile = true`** (S3-native locking), `default_tags` `Project` + `ManagedBy`. |
| `infra/variables.tf` | Settings (Region, instance type, shard count, Firehose buffer, speed limit, scan limits per workgroup, the Lake Formation cross-account version) and the **phase switches**: `history_ready`, `alerts_efo`, `quicksight_principal_arn` (validated as a Quick Sight ARN). |
| `infra/main.tf` | Names, and the column list in one place: the 11 columns of a ping and the analyst's 10-column allow-list. |
| `infra/network.tf` | VPC `10.130.0.0/16`, one public subnet, internet gateway, route, the S3 gateway endpoint, a security group with no inbound rules and an explicit egress rule. |
| `infra/storage.tf` | Three buckets (lake, Athena results, code) with public access block, SSE-S3 and a TLS-only policy each (`for_each`), lifecycle rules (results expire after 7 days), and the tool files as `aws_s3_object` (etag = MD5). |
| `infra/stream.tf` | The stream, the optional enhanced fan-out consumer, the alert function, its log group and its event source mapping (which switches source with `alerts_efo`). |
| `infra/firehose.tf` | The delivery stream with JSON → Parquet conversion from the Glue schema, and its log group. |
| `infra/catalog.tf` | The `mvela_fleet` database (created after the Lake Formation settings), `raw_pings_json`, and `fleet_live` with partition projection on `dt`. |
| `infra/lakeformation.tf` | The account's data lake settings, the registration role, the registered `curated/` location, the grants. |
| `infra/athena.tf` | Three workgroups: engineering (20 GB/query, enforced), analysts (1 GB/query, enforced), migration (not enforced, for the CTAS). |
| `infra/iam.tf` | One role per job: simulator, Firehose, alert function, analyst. |
| `infra/compute.tf` | The simulator: AL2023 from the SSM parameter, IMDSv2 required, encrypted gp3, boot script from `templates/userdata.sh.tftpl`. |
| `infra/alarms.tf` | Lake freshness and alert iterator age. |

`fleet_history` is the one table Terraform doesn't create: the CTAS makes it, and Terraform only grants on it once it exists. Deleting the database at destroy deletes it with the rest.

## Phases

Each phase is one line in `infra/phases.auto.tfvars` (git-ignored: it's run state, not code), read by every plan and apply.

| Phase | Line | Plan | Result |
|---|---|---|---|
| Base | (none) | `60 to add, 0 to change, 0 to destroy` | `Apply complete! Resources: 60 added`; state list 64 (60 + 4 data sources) |
| Migration workgroup | (code added during the build) | `1 to add` | `mvela-migration` created |
| History grant | `history_ready = true` | `1 to add` | `1 added` |
| Enhanced fan-out | `alerts_efo = true` | `2 to add, 1 to change, 1 to destroy` | `2 added, 1 changed, 1 destroyed` |
| Dashboard grant | `quicksight_principal_arn = "..."` | (plan not saved) | `1 added` |
| Dashboard grant removed | line deleted | `1 to destroy` | `0 added, 0 changed, 1 destroyed` |
| Before destroy | `terraform state rm aws_lakeformation_data_lake_settings.this` | | out of the state: the destroy plan counts 62, not 63 |
| Destroy | | `0 to add, 0 to change, 62 to destroy` | **`Destroy complete! Resources: 62 destroyed.`** |

From this repo the base plan is **61**: the migration workgroup is part of `athena.tf` now. 61 + 1 history grant + 1 consumer − the settings removed from state = 62 destroyed.

Screenshots: [`03`](screenshots/03-plan-lake-formation-admin.png), [`04`](screenshots/04-apply-base-60-added.png), [`05`](screenshots/05-saved-outputs-state-list.png), [`14`](screenshots/14-history-grant-plan-and-apply.png), [`27`](screenshots/27-enhanced-fan-out-plan-and-apply.png), [`42`](screenshots/42-quick-sight-grant-applied.png)–[`44`](screenshots/44-quick-sight-grant-removed.png), [`52`](screenshots/52-destroy-plan-workgroups.png), [`53`](screenshots/53-destroy-complete-62.png). Plans in [`results/raw/`](results/raw/).

## Things Terraform taught me in this build

- **Some resources manage an account, not a project.** `aws_lakeformation_data_lake_settings` replaces the whole settings object on create and, going by the provider's implementation, clears it on delete and sets the cross-account version to `"1"`. Terraform's ownership model doesn't fit something that existed before the project and must outlive it, so the resource leaves the state before the destroy and a script restores the snapshot ([ADR 0006](adr/0006-snapshot-and-restore-the-account-wide-lake-formation-settings.md)).
- **Pin every value the API will echo back.** The settings' `parameters` map holds both `CROSS_ACCOUNT_VERSION` and `SET_CONTEXT`; declaring both, exactly as the API returns them, keeps later plans from showing a difference.
- **Order matters across services.** The database waits for the Lake Formation settings (so it's created without the `IAMAllowedPrincipals` grant), and Firehose waits for its Lake Formation grant (its first schema read would fail otherwise). Both are `depends_on` in the code.
- **A changed source is a replacement.** An event source mapping can't move from a stream to a consumer in place; the plan said `must be replaced`, and the apply destroyed the old mapping before creating the new one.
- **Verify through AWS, not through Terraform.** After the apply I described the stream, Firehose, the Glue tables, the Lake Formation settings and grants, and the workgroup with the AWS CLI, and compared every tool file's SHA-256 on the server with Terraform's output ([`06`](screenshots/06-kinesis-stream-summary.png)–[`10`](screenshots/10-simulator-ready-code-hashes-match.png)).

## Quality gates

`terraform fmt -check -recursive` (clean), `terraform validate` (`Success! The configuration is valid.`), `tflint --recursive` with the recommended rules (clean), and `checkov` with `--soft-fail`: **139 passed, 36 failed, 0 skipped** ([`02`](screenshots/02-quality-gates-fmt-validate-tflint-checkov.png), [`results/raw/checkov.txt`](results/raw/checkov.txt)). The scan covers `bootstrap/` too, so the state bucket appears in it. Each finding, and what I decided:

| Check | Resource(s) | Decision for this lab | In production |
|---|---|---|---|
| CKV_AWS_145 S3 encrypted with KMS by default | state, lake, results, code | accepted: SSE-S3 | KMS on the lake and state buckets (`aws-kms-encryption-architecture`) |
| CKV_AWS_18 S3 access logging | state, lake, results, code | accepted | access logs on the lake and state buckets |
| CKV_AWS_144 S3 cross-Region replication | state, lake, results, code | accepted | replicate the lake if it's the system of record |
| CKV2_AWS_62 S3 event notifications | state, lake, results, code | not needed | not needed |
| CKV_AWS_21 S3 versioning | lake, results, code | accepted: the lake is rebuilt by the build; results and code are disposable | versioning on the lake |
| CKV2_AWS_61 lifecycle configuration | code | not needed: rebuilt from the repo every time | not needed |
| CKV_AWS_300 abort incomplete uploads | state bucket's lifecycle | **fix**: add `abort_incomplete_multipart_upload` to the bootstrap (lake and results already have it) | fix |
| CKV_AWS_88 public IP | simulator | accepted: outbound only, no inbound rules | private subnet + VPC endpoints (`aws-private-connectivity-endpoints`) |
| CKV_AWS_126 / CKV_AWS_135 detailed monitoring, EBS-optimised | simulator | not needed for a test client (c7i is EBS-optimised by default; the check reads the argument) | set them explicitly |
| CKV2_AWS_11 VPC flow logs | VPC | accepted for a lab | flow logs on |
| CKV2_AWS_12 default security group | VPC | **fix**: manage the default group with no rules | fix |
| CKV_AWS_158 / CKV_AWS_338 log group KMS, 1-year retention | Firehose and function log groups | accepted: 7 days, deleted at destroy | KMS + retention set by policy |
| CKV_AWS_117 / CKV_AWS_116 / CKV_AWS_115 / CKV_AWS_50 / CKV_AWS_272 / CKV_AWS_173 Lambda in a VPC, DLQ, concurrency limit, X-Ray, code signing, environment variable encryption | alert function | accepted for the lab: it reads a stream and writes logs; its only environment variables are the speed limit and the mode | an on-failure destination on the mapping, a concurrency limit, X-Ray; code signing where policy requires it |

36 findings: 4 × 4 on the buckets, 3 versioning, 2 × 2 on the log groups, and 13 single ones.
