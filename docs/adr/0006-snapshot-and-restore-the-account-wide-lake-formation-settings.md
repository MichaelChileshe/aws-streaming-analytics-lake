# 0006 · Snapshot the account-wide Lake Formation settings, remove them from state before destroy, restore and diff

**Status:** accepted · 2026-10-09

## Context
`aws_lakeformation_data_lake_settings` manages one object per account: the data lake administrators, the default permissions for new databases and tables, and parameters such as the cross-account version. This project needs it changed (me as administrator, no `IAMAllowedPrincipals` default), but the object existed before the project and must be the same after it. Going by the provider's implementation, its delete clears the object and sets the cross-account version to `"1"`, which is not what the account had (`"4"`). Left cleared, every database created later in the account, by any project, would be Lake Formation-only.

## Decision
1. **Snapshot** before the first apply (`scripts/lf_settings.py snapshot`), refusing to overwrite an existing snapshot.
2. **Declare the parameters the account already has** (`CROSS_ACCOUNT_VERSION` from a variable, `SET_CONTEXT = "TRUE"`), so the build changes only what it needs.
3. **Before the destroy, `terraform state rm`** the settings resource, so its delete never runs and I stay administrator while the grants are revoked.
4. **After the destroy, restore** the snapshot (`put-data-lake-settings`) and **diff** it against the live settings.
5. Create Athena's `default` database before the first apply, while it still gets the IAM-only default.

## Alternatives considered
- **Let `terraform destroy` delete it:** clears admins and defaults, and changes the cross-account version.
- **Manage the settings outside Terraform entirely:** the project's access model would depend on a manual step not visible in the plan.
- **A separate, long-lived Terraform stack for account settings:** the right shape for an organisation with many lakes; more than one project needs.

## Consequences
- Measured: after the destroy the settings were still the project's; after the restore, `identical to the snapshot taken before the build`.
- During the build, any new Glue database in the account would have been Lake Formation-only, so no other project created Glue databases or tables while this one existed.
- The teardown has one step outside `terraform destroy`, documented in [`../teardown.md`](../teardown.md).
