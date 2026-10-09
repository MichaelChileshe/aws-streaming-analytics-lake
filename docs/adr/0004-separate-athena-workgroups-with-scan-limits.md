# 0004 · Separate Athena workgroups with scan limits, and a non-enforcing one for migrations only

**Status:** accepted · 2026-10-09

## Context
Engineers and analysts query the same catalog for different purposes and with different risks: an engineer may legitimately scan gigabytes; an analyst's mistaken query should fail cheaply. Query results can contain personal data. A CTAS needs to choose where its table's files go, which an enforcing workgroup refuses.

## Decision
- **`mvela-engineering`:** 20 GB per query, settings enforced, results in `engineering/`.
- **`mvela-analysts`:** 1 GB per query, settings enforced, results in `analysts/`; the analyst role's IAM policy allows only this workgroup.
- **`mvela-migration`:** 20 GB per query, **not enforced**, results in `migration/`, used only for the CTAS.
- Results expire after 7 days; all three publish CloudWatch metrics.

## Alternatives considered
- **One workgroup for everyone:** no way to limit the analyst's scans or separate their results from engineering's.
- **Turning enforcement off on the engineering workgroup for the CTAS:** every engineering query could then send its results anywhere and skip encryption.

## Consequences
- Measured: the analyst's query in `mvela-engineering` was refused by IAM (`AccessDeniedException`); the CTAS ran in `mvela-migration` after being rejected in an enforcing workgroup.
- The 1 GB limit caps a mistaken analyst query at about half a cent; it would also stop a legitimate analyst query over the raw export, which is the point.
- Who may use `mvela-migration` is controlled by IAM; in this lab only the administrator could.
