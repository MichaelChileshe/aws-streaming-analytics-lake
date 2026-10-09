#!/usr/bin/env python3
"""The account's Lake Formation settings: snapshot them before the build, restore them after.

Terraform's aws_lakeformation_data_lake_settings REPLACES the account-wide settings when it is
created, and its delete would CLEAR them (no admins, no default permissions, cross-account
version 1). Neither puts back what the account had before, so the teardown removes it from
Terraform's state instead, and I put the copy back myself.

  python3 scripts/lf_settings.py snapshot     # before the first apply: build/results/lf-settings-before.json
  python3 scripts/lf_settings.py show         # the settings right now, in short
  python3 scripts/lf_settings.py restore      # after the destroy: put the snapshot back
  python3 scripts/lf_settings.py diff         # now vs the snapshot: "identical" is the goal
"""
import json
import os
import sys
import tempfile

from kit_aws import RESULTS, aws

SNAP = os.path.join(RESULTS, "lf-settings-before.json")
KEYS = ("DataLakeAdmins", "ReadOnlyAdmins", "CreateDatabaseDefaultPermissions", "CreateTableDefaultPermissions",
        "TrustedResourceOwners", "AllowExternalDataFiltering", "AllowFullTableExternalDataAccess",
        "ExternalDataFilteringAllowList", "AuthorizedSessionTagValueList", "Parameters")


def current():
    return aws("lakeformation", "get-data-lake-settings")["DataLakeSettings"]


def summary(s):
    who = lambda lst: [p["DataLakePrincipalIdentifier"].split(":")[-1] for p in lst or []]
    perms = lambda lst: [f"{p['Principal']['DataLakePrincipalIdentifier']}={','.join(p['Permissions'])}" for p in lst or []]
    return {"admins": who(s.get("DataLakeAdmins")),
            "new_database_defaults": perms(s.get("CreateDatabaseDefaultPermissions")),
            "new_table_defaults": perms(s.get("CreateTableDefaultPermissions")),
            "parameters": s.get("Parameters", {})}


def norm(s):
    """Comparable form: only the settable keys, empty lists treated like missing ones."""
    return {k: s.get(k) for k in KEYS if s.get(k) not in (None, [], {}, False)}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "snapshot":
        os.makedirs(RESULTS, exist_ok=True)
        if os.path.exists(SNAP):
            sys.exit(f"{SNAP} already exists: it must be the settings from BEFORE the build, so I won't overwrite it.")
        s = current()
        json.dump(s, open(SNAP, "w"), indent=1)
        print(json.dumps(summary(s), indent=1))
        print(f"RESULT lf-settings snapshot saved: {SNAP}")
    elif cmd == "show":
        print(json.dumps(summary(current()), indent=1))
    elif cmd == "restore":
        before = json.load(open(SNAP))
        body = {k: v for k, v in before.items() if k in KEYS}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(body, f)
        aws("lakeformation", "put-data-lake-settings", "--data-lake-settings", f"file://{f.name}")
        os.unlink(f.name)
        print(json.dumps(summary(current()), indent=1))
        print("RESULT lf-settings restored from the snapshot")
    elif cmd == "diff":
        before, now = norm(json.load(open(SNAP))), norm(current())
        if before == now:
            print("RESULT lf-settings: identical to the snapshot taken before the build")
            return 0
        print("before:", json.dumps(summary(json.load(open(SNAP))), indent=1))
        print("now:   ", json.dumps(summary(current()), indent=1))
        print("RESULT lf-settings: DIFFERENT from the snapshot")
        return 1
    else:
        sys.exit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
